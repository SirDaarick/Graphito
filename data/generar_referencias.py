#!/usr/bin/env python3
import argparse
import csv
import json
import sys
import random
from datetime import datetime
from pathlib import Path

import config
from modelos import create_provider_from_config


def load_enunciados(enunciados_path: Path) -> dict[tuple, dict]:
    enunciados = {}
    
    if not enunciados_path.exists():
        print(f"Error: {enunciados_path} no existe. Ejecuta primero extraer_enunciados.py")
        sys.exit(1)
    
    with enunciados_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["curso"], row["carpeta"], row["subcarpeta"])
            enunciados[key] = {
                "enunciado": row["enunciado"],
                "lenguaje": row["lenguaje"]
            }
    
    return enunciados


def find_student_codes(problem_path: Path) -> list[Path]:
    codes = []
    codes = list(problem_path.glob("*.c")) + list(problem_path.glob("*.cpp"))
    return codes


def generate_reference(
    provider,
    enunciado: str,
    codigo_original: str,
    modelo_name: str,
    version: int
) -> str:
    prompt = config.PROMPT_REFERENCIA.format(
        enunciado=enunciado,
        codigo_original=codigo_original[:1500]
    )
    
    response = provider.generate(prompt)
    
    code = response
    if "```c" in code:
        code = code.split("```c")[1].split("```")[0]
    elif "```cpp" in code:
        code = code.split("```cpp")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]
    
    code = code.strip()
    
    return code


def save_reference(
    output_dir: Path,
    asignacion: str,
    code: str,
    metadata: dict
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"referencia_v{metadata['version']}_{metadata['modelo']}.c"
    file_path = output_dir / filename
    
    file_path.write_text(code, encoding="utf-8")
    
    meta_path = output_dir / "metadata.json"
    if meta_path.exists():
        meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta_data = {"references": []}
    
    meta_data["references"].append(metadata)
    meta_path.write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    return file_path


def main():
    parser = argparse.ArgumentParser(
        description="Generar versiones de código mediante LLM"
    )
    parser.add_argument(
        "--model",
        default=config.DEFAULT_MODEL,
        choices=list(config.MODELS.keys()),
        help="Modelo LLM a usar"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Lista de modelos a usar (sobreescribe --model)"
    )
    parser.add_argument(
        "--versions",
        default=config.VERSIONS_PER_PROBLEM,
        type=int,
        help="Número de versiones a generar por problema"
    )
    parser.add_argument(
        "--enunciados",
        default=str(config.ENUNCIADOS_PATH),
        help="Archivo CSV con enunciados"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limitar a N problemas (para pruebas)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar salida detallada"
    )
    
    args = parser.parse_args()
    
    modelos = args.models if args.models else [args.model]
    
    print(f"Modelos: {modelos}")
    print(f"Versiones por problema: {args.versions}")
    
    enunciados = load_enunciados(Path(args.enunciados))
    print(f"Cargados {len(enunciados)} enunciados")
    
    problemas = []
    for (curso, carpeta, subcarpeta), data in enunciados.items():
        problemas.append({
            "curso": curso,
            "carpeta": carpeta,
            "subcarpeta": subcarpeta,
            "enunciado": data["enunciado"],
            "lenguaje": data["lenguaje"]
        })
    
    if args.limit:
        problemas = problemas[:args.limit]
    
    print(f"Procesando {len(problemas)} problemas...")
    
    for i, problema in enumerate(problemas):
        problema_path = config.DATASET_PATH / problema["curso"] / problema["carpeta"] / problema["subcarpeta"]
        
        if not problema_path.exists():
            print(f"[{i+1}/{len(problemas)}] Saltando {problema['curso']}/{problema['carpeta']}/{problema['subcarpeta']} - path no encontrado")
            continue
        
        student_codes = find_student_codes(problema_path)
        if not student_codes:
            print(f"[{i+1}/{len(problemas)}] Saltando - sin archivos de código")
            continue
        
        codigo_original = random.choice(student_codes).read_text(encoding="utf-8", errors="ignore")
        
        asignacion_key = f"{problema['curso']}/{problema['carpeta']}/{problema['subcarpeta']}"
        output_dir = config.OUTPUT_PATH / problema["curso"] / problema["carpeta"] / problema["subcarpeta"]
        
        print(f"[{i+1}/{len(problemas)}] {asignacion_key} ({problema['enunciado'][:30]}...)")
        
        for modelo_name in modelos:
            model_config = config.MODELS.get(modelo_name)
            if not model_config:
                print(f"  Modelo {modelo_name} no encontrado, saltando")
                continue
            
            try:
                provider = create_provider_from_config(model_config)
            except Exception as e:
                print(f"  Error creando provider {modelo_name}: {e}")
                continue
            
            for v in range(1, args.versions + 1):
                try:
                    code = generate_reference(
                        provider,
                        problema["enunciado"],
                        codigo_original,
                        modelo_name,
                        v
                    )
                    
                    metadata = {
                        "asignacion": asignacion_key,
                        "enunciado": problema["enunciado"],
                        "codigo_original": problema_path.name,
                        "modelo": modelo_name,
                        "version": v,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    file_path = save_reference(output_dir, asignacion_key, code, metadata)
                    
                    if args.verbose:
                        print(f"    -> {file_path.name}")
                    else:
                        print(f"    -> v{v} {modelo_name}")
                        
                except Exception as e:
                    print(f"    Error: {e}")
                    continue
    
    print(f"\nCompletado! Referencias guardadas en {config.OUTPUT_PATH}")


if __name__ == "__main__":
    main()