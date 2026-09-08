#!/usr/bin/env python3
"""
indent_only.py - Indentador selectivo para código C/C++

Propósito: Normalizar ÚNICAMENTE la indentación de archivos fuente C/C++
dejando intacto TODO lo demás: espacios alrededor de operadores, posición
de llaves, estilo de comentarios, nombres de variables, etc.

Esto simula el comportamiento de un IDE moderno que solo auto-indenta
sin reformatear el estilo del programador.

Mejoras:
- Paralelización por carpeta de problema (cada worker toma una carpeta Z*)
- Estado persistente para saltear archivos ya indentados
- Modo sample para pruebas rápidas sin procesar todo
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial


def get_file_hash(file_path: Path) -> str:
    """Hash rápido del contenido + mtime para detectar cambios."""
    stat = file_path.stat()
    return hashlib.sha256(f"{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()[:16]


def load_state(state_file: Path) -> dict:
    """Carga el estado de archivos ya procesados."""
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state_file: Path, state: dict):
    """Guarda el estado de archivos procesados."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def calculate_indent_level(lines: list[str]) -> list[int]:
    """
    Calcula el nivel de indentación para cada línea basado en llaves.
    
    Heurística:
    - '{' al final de línea o solo -> aumenta nivel para siguientes líneas
    - '}' al inicio de línea o solo -> disminuye nivel para línea actual y siguientes
    - Ignora llaves dentro de strings/comentarios (básico, incluye multilinea)
    
    Returns: lista de niveles de indentación (0, 1, 2, ...)
    """
    levels = []
    current_level = 0
    in_multiline_comment = False
    
    for line in lines:
        stripped = line.strip()
        
        # Si la línea está vacía, mantener nivel actual (sin indentar)
        if not stripped:
            levels.append(0)
            continue
        
        # Calcular nivel de indentación para ESTA línea
        if stripped.startswith('}'):
            line_level = max(0, current_level - 1)
        else:
            line_level = current_level
        
        levels.append(line_level)
        
        # Extraer solo código real (sin strings, comentarios)
        code_only = extract_code_only(stripped, in_multiline_comment)
        
        # Actualizar estado de comentario multilinea para la siguiente línea
        in_multiline_comment = code_only['still_in_multiline_comment']
        
        # Ajustar current_level para la SIGUIENTE línea basado en net braces
        open_braces = code_only['open_braces']
        close_braces = code_only['close_braces']
        net_braces = open_braces - close_braces
        current_level = max(0, current_level + net_braces)
    
    return levels


def extract_code_only(text: str, starts_in_multiline_comment: bool = False) -> dict:
    """
    Extrae solo código real de una línea, ignorando strings y comentarios.
    También rastrea si la línea deja abierto un comentario multilinea.
    
    Returns:
        dict con:
        - 'open_braces': int, count de '{' reales
        - 'close_braces': int, count de '}' reales  
        - 'still_in_multiline_comment': bool, si quedamos dentro de /* */
    """
    open_count = 0
    close_count = 0
    in_string = False
    string_char = None
    in_comment = starts_in_multiline_comment
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # Si estamos en un comentario multilinea, buscar cierre
        if in_comment:
            if char == '*' and i + 1 < len(text) and text[i+1] == '/':
                in_comment = False
                i += 2
                continue
            i += 1
            continue
        
        # Manejo de strings
        if char in ('"', "'") and not in_string:
            in_string = True
            string_char = char
            i += 1
            continue
        elif char == string_char and in_string:
            # Verificar escape
            if i > 0 and text[i-1] == '\\':
                i += 1
                continue
            in_string = False
            string_char = None
            i += 1
            continue
        
        if in_string:
            i += 1
            continue
        
        # Manejo de comentarios de línea
        if char == '/' and i + 1 < len(text) and text[i+1] == '/':
            break  # Resto de línea es comentario
        
        # Manejo de comentarios multilinea
        if char == '/' and i + 1 < len(text) and text[i+1] == '*':
            in_comment = True
            i += 2
            continue
        
        # Contar llaves reales
        if char == '{':
            open_count += 1
        elif char == '}':
            close_count += 1
        
        i += 1
    
    return {
        'open_braces': open_count,
        'close_braces': close_count,
        'still_in_multiline_comment': in_comment
    }


def indent_line(line: str, level: int, indent_size: int = 4, use_tabs: bool = False) -> str:
    """
    Aplica indentación a una línea preservando todo el contenido original.
    """
    stripped = line.lstrip()
    
    # Si la línea está vacía, devolver tal cual (preserva líneas en blanco)
    if not stripped:
        return line
    
    indent_str = '\t' * level if use_tabs else ' ' * (indent_size * level)
    return indent_str + stripped


def process_file(input_path: Path, output_path: Path = None,
                 indent_size: int = 4, use_tabs: bool = False,
                 dry_run: bool = False) -> dict:
    """
    Procesa un archivo .c o .cpp aplicando solo indentación.
    
    Returns:
        dict con 'success', 'input_path', 'output_path', 'lines_changed'
    """
    try:
        content = input_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return {'success': False, 'input_path': str(input_path), 'error': str(e)}
    
    # Normalizar saltos de línea
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')
    
    # Calcular niveles de indentación
    levels = calculate_indent_level(lines)
    
    # Aplicar indentación
    new_lines = []
    lines_changed = 0
    
    for i, (line, level) in enumerate(zip(lines, levels)):
        new_line = indent_line(line, level, indent_size, use_tabs)
        new_lines.append(new_line)
        
        # Contar cambios (solo si cambió la indentación, no el contenido)
        old_stripped = line.lstrip()
        new_stripped = new_line.lstrip()
        if old_stripped == new_stripped and line != new_line:
            lines_changed += 1
    
    new_content = '\n'.join(new_lines)
    
    # Si no se especificó output_path, sobrescribir
    if output_path is None:
        output_path = input_path
    
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(new_content, encoding='utf-8')
    
    return {
        'success': True,
        'input_path': str(input_path),
        'output_path': str(output_path),
        'lines_changed': lines_changed,
        'total_lines': len(lines)
    }


def process_directory_batch(dir_batch: tuple, input_dir: Path, output_dir: Path = None,
                            indent_size: int = 4, use_tabs: bool = False,
                            extensions: tuple = ('.c', '.cpp', '.h', '.hpp'),
                            dry_run: bool = False, state: dict = None,
                            state_file: Path = None) -> list[dict]:
    """
    Procesa un lote de archivos (todos de una misma carpeta problema).
    Cada worker ejecuta esto secuencialmente para su lote asignado.
    """
    results = []
    local_state_updates = {}
    
    for file_path in dir_batch:
        # Verificar si ya fue procesado y no cambió
        file_key = str(file_path.relative_to(input_dir))
        current_hash = get_file_hash(file_path)
        
        if state and file_key in state:
            if state[file_key] == current_hash:
                results.append({
                    'success': True,
                    'input_path': str(file_path),
                    'skipped': True,
                    'lines_changed': 0,
                    'total_lines': 0
                })
                continue
        
        # Procesar
        if output_dir is not None:
            rel_path = file_path.relative_to(input_dir)
            out_path = output_dir / rel_path
        else:
            out_path = None
        
        result = process_file(file_path, out_path, indent_size, use_tabs, dry_run)
        results.append(result)
        
        # Registrar en estado local (hash del archivo YA PROCESADO)
        if result.get('success') and not dry_run:
            # Recalcular hash después de escribir para detectar archivos ya indentados
            processed_hash = get_file_hash(file_path)
            local_state_updates[file_key] = processed_hash
    
    # Guardar estado parcial al finalizar el lote (solo si hay algo que guardar)
    if local_state_updates and state_file and not dry_run:
        # Usamos un lockfile simple basado en archivo para evitar corrupción
        lock_file = state_file.with_suffix('.json.lock')
        max_retries = 10
        for attempt in range(max_retries):
            try:
                if not lock_file.exists():
                    lock_file.write_text("lock", encoding='utf-8')
                    # Recargar estado actual (otro worker pudo haber escrito)
                    current_state = load_state(state_file)
                    current_state.update(local_state_updates)
                    save_state(state_file, current_state)
                    lock_file.unlink(missing_ok=True)
                    break
                else:
                    time.sleep(0.05 * (attempt + 1))
            except OSError:
                time.sleep(0.05 * (attempt + 1))
        else:
            # Si no pudo adquirir lock, guarda en archivo parcial
            partial_file = state_file.with_suffix(f'.partial.{id(dir_batch)}.json')
            partial_state = load_state(partial_file)
            partial_state.update(local_state_updates)
            save_state(partial_file, partial_state)
    
    return results


def process_directory(input_dir: Path, output_dir: Path = None,
                      indent_size: int = 4, use_tabs: bool = False,
                      extensions: tuple = ('.c', '.cpp', '.h', '.hpp'),
                      num_workers: int = None, dry_run: bool = False,
                      state_file: Path = None, sample: int = None) -> list[dict]:
    """
    Procesa recursivamente todos los archivos C/C++ en un directorio.
    Paralelizado por CARPETAS DE PROBLEMA (cada worker toma una carpeta Z* entera).
    """
    # Encontrar todos los archivos
    files = []
    for ext in extensions:
        files.extend(input_dir.rglob(f'*{ext}'))
    
    if not files:
        print(f"No se encontraron archivos {extensions} en {input_dir}")
        return []
    
    # Ordenar para reproducibilidad
    files = sorted(files)
    
    # Modo sample: limitar cantidad total
    if sample is not None and sample > 0:
        files = files[:sample]
        print(f"[MODO SAMPLE] Procesando solo {len(files)} archivos de prueba")
    else:
        print(f"Encontrados {len(files)} archivos para procesar")
    
    # Cargar estado previo
    state = load_state(state_file) if state_file else {}
    already_done = sum(1 for f in files if str(f.relative_to(input_dir)) in state)
    if already_done > 0:
        print(f"{already_done} archivos ya indentados previamente (se saltarán)")
    
    # Agrupar por carpeta de problema (segundo nivel desde input_dir, ej: A2016/Z1)
    # Esto asegura que cada worker tome una carpeta completa
    dir_groups = {}
    for f in files:
        try:
            rel = f.relative_to(input_dir)
            # Usar hasta 2 niveles de profundidad como identificador de grupo
            if len(rel.parts) >= 2:
                group_key = str(Path(rel.parts[0]) / rel.parts[1])
            else:
                group_key = str(rel.parts[0]) if rel.parts else "root"
        except ValueError:
            group_key = "root"
        
        dir_groups.setdefault(group_key, []).append(f)
    
    # Preparar lotes (cada lote = una carpeta de problema)
    batches = list(dir_groups.values())
    print(f"Agrupados en {len(batches)} carpetas de problema")
    
    # Preparar output
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Paralelizar por lotes (cada lote es una carpeta)
    num_workers = num_workers or min(cpu_count(), len(batches), 8)
    print(f"Usando {num_workers} workers paralelos (uno por carpeta)...")
    
    process_func = partial(
        process_directory_batch,
        input_dir=input_dir,
        output_dir=output_dir,
        indent_size=indent_size,
        use_tabs=use_tabs,
        extensions=extensions,
        dry_run=dry_run,
        state=state,
        state_file=state_file
    )
    
    all_results = []
    if len(batches) == 1 or num_workers == 1:
        # Sin paralelismo si solo hay un lote
        for batch in batches:
            all_results.extend(process_func(batch))
    else:
        with Pool(num_workers) as pool:
            batch_results = pool.map(process_func, batches)
            for res in batch_results:
                all_results.extend(res)
    
    # Merge de archivos de estado parciales si existen
    if state_file and state_file.exists():
        main_state = load_state(state_file)
        partial_files = list(state_file.parent.glob(f"{state_file.stem}.partial.*.json"))
        for pf in partial_files:
            try:
                partial_state = load_state(pf)
                main_state.update(partial_state)
                pf.unlink(missing_ok=True)
            except OSError:
                pass
        save_state(state_file, main_state)
    
    # Reporte
    successful = sum(1 for r in all_results if r.get('success'))
    skipped = sum(1 for r in all_results if r.get('skipped'))
    processed = successful - skipped
    total_changed = sum(r.get('lines_changed', 0) for r in all_results if r.get('success'))
    
    print(f"\nCompletado: {processed} procesados, {skipped} saltados, {len(all_results) - successful} errores")
    print(f"Total de líneas con indentación ajustada: {total_changed}")
    
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Indentador selectivo para código C/C++ del dataset IEEE"
    )
    parser.add_argument(
        "input", type=Path, nargs="?", default=None,
        help="Archivo o directorio de entrada (default: dataset raw desde config.py)"
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Directorio de salida (default: sobrescribe entrada)"
    )
    parser.add_argument(
        "--indent-size", "-i", type=int, default=4,
        help="Tamaño de indentación en espacios (default: 4)"
    )
    parser.add_argument(
        "--tabs", "-t", action="store_true",
        help="Usar tabs en vez de espacios"
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=None,
        help="Número de workers paralelos (default: auto, uno por carpeta problema)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Simular sin escribir archivos"
    )
    parser.add_argument(
        "--extensions", default=".c,.cpp,.h,.hpp",
        help="Extensiones a procesar (default: .c,.cpp,.h,.hpp)"
    )
    parser.add_argument(
        "--state-file", type=Path, default=None,
        help="Archivo JSON para trackear archivos ya procesados (default: input_dir/.indent_state.json)"
    )
    parser.add_argument(
        "--sample", "-s", type=int, default=None,
        help="Modo prueba: procesar solo N archivos (útil para validar antes de correr todo)"
    )
    parser.add_argument(
        "--reset-state", action="store_true",
        help="Borrar estado previo y reprocesar todo"
    )
    
    args = parser.parse_args()
    
    # Si no se pasó input, usar la ruta por defecto desde config.py
    if args.input is None:
        config_path = Path(__file__).parent / "config.py"
        if config_path.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("config", config_path)
                config = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config)
                args.input = Path(config.DATASET_PATH)
                print(f"Usando dataset por defecto: {args.input}")
            except Exception as e:
                print(f"⚠️  config.py existe pero falló al cargar: {e}", file=sys.stderr)
                # Fallback a ruta conocida
                args.input = Path(__file__).parent / "raw" / "src"
                print(f"Usando fallback: {args.input}")
        else:
            args.input = Path(__file__).parent / "raw" / "src"
            print(f"Usando fallback (no hay config.py): {args.input}")
    
    if not args.input.exists():
        print(f"❌ Error: {args.input} no existe", file=sys.stderr)
        sys.exit(1)
    
    extensions = tuple(args.extensions.split(','))
    
    # Determinar archivo de estado
    state_file = args.state_file
    if state_file is None and args.input.is_dir():
        state_file = args.input / ".indent_state.json"
    
    # Resetear estado si se pidió
    if args.reset_state and state_file and state_file.exists():
        state_file.unlink()
        print("Estado previo borrado. Se reprocesará todo.")
    
    if args.input.is_file():
        result = process_file(
            args.input, args.output,
            args.indent_size, args.tabs, args.dry_run
        )
        if result['success']:
            print(f"✅ {result['input_path']}")
            print(f"   Líneas ajustadas: {result['lines_changed']}/{result['total_lines']}")
            if args.dry_run:
                print("   (modo simulación - no se escribió nada)")
        else:
            print(f"❌ Error: {result.get('error')}")
    else:
        results = process_directory(
            args.input, args.output,
            args.indent_size, args.tabs,
            extensions, args.workers, args.dry_run,
            state_file, args.sample
        )
        
        # Mostrar errores si los hay
        errors = [r for r in results if not r.get('success')]
        if errors:
            print(f"\n⚠️  {len(errors)} errores:")
            for e in errors[:5]:
                print(f"   - {e['input_path']}: {e.get('error')}")


if __name__ == "__main__":
    main()
