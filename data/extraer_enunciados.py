#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

import config
from modelos import create_provider_from_config


def find_problem_folders(base_path: Path) -> list[tuple[str, str, str]]:
    problems = []
    
    for curso_dir in base_path.iterdir():
        if not curso_dir.is_dir():
            continue
        curso = curso_dir.name
        
        for asignacion_dir in curso_dir.iterdir():
            if not asignacion_dir.is_dir():
                continue
            asignacion = asignacion_dir.name
            
            for tarea_dir in asignacion_dir.iterdir():
                if not tarea_dir.is_dir():
                    continue
                tarea = tarea_dir.name
                
                problemas.append((curso, asignacion, tarea))
    
    return problemas


def read_sample_codes(problem_path: Path, num_samples: int = 2) -> list[str]:
    codes = []
    code_files = list(problem_path.glob("*.c")) + list(problem_path.glob("*.cpp"))
    
    for f in code_files[:num_samples]:
        try:
            codes.append(f.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
    
    return codes


def parse_llm_response(response: str) -> tuple[str, str]:
    response = response.strip()
    
    if "|" in response:
        parts = response.split("|")
        enunciado = parts[0].replace("Enunciado:", "").strip()
        lenguaje = parts[1].replace("Lenguaje:", "").strip()
    else:
        lines = response.split("\n")
        enunciado = ""
        lenguaje = "C"
        
        for line in lines:
            if line.startswith("Enunciado:"):
                enunciado = line.replace("Enunciado:", "").strip()
            elif line.startswith("Lenguaje:"):
                lenguaje = line.replace("Lenguaje:", "").strip()
        
        if not enunciado:
            enunciado = response[:100]
    
    return enunciado, lenguaje


def main():
    parser = argparse.ArgumentParser(
        description="Extraer enunciados del dataset usando LLM"
    )
    parser.add_argument(
        "--model", 
        default=config.DEFAULT_MODEL,
        choices=list(config.MODELS.keys()),
        help="Modelo LLM a usar"
    )
    parser.add_argument(
        "--output", 
        default=str(config.ENUNCIADOS_PATH),
        help="Archivo CSV de salida"
    )
    parser.add_argument(
        "--num-samples",
        default=config.NUM_EJEMPLOS_ANALISIS,
        type=int,
        help="Número de muestras de código por problema"
    )
    parser.add_argument(
        "--force", 
        action="store_true",
       help="Sobrescribir archivo existente"
    )
    
    args = parser.parse_args()
    
    model_config = config.MODELS.get(args.model)
    if not model_config:
        print(f"Error: Modelo '{args.model}' no encontrado", file=sys.stderr)
        sys.exit(1)
    
    if config.ENUNCIADOS_PATH.exists() and not args.force:
        print(f"Archivo {args.output} ya existe. Usa --force para sobrescribir.")
        sys.exit(1)
    
    print(f"Usando modelo: {args.model} ({model_config['provider']}/{model_config['model']})")
    
    provider = create_provider_from_config(model_config)
    
    problems = find_problem_folders(config.DATASET_PATH)
    print(f"Encontrados {len(problems)} problemas en el dataset")
    
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["curso", "carpeta", "subcarpeta", "enunciado", "lenguaje"])
        
        for i, (curso, asignacion, tarea) in enumerate(problems):
            problem_path = config.DATASET_PATH / curso / asignacion / tarea
            
            if not problem_path.exists():
                print(f"[{i+1}/{len(problems)}]skipping {curso}/{asignacion}/{tarea} - path not found")
                continue
            
            codes = read_sample_codes(problem_path, args.num_samples)
            
            if len(codes) < 1:
                print(f"[{i+1}/{len(problems)}]skipping {curso}/{asignacion}/{tarea} - no code files")
                continue
            
            code1 = codes[0][:2000]
            code2 = codes[1][:2000] if len(codes) > 1 else ""
            
            prompt = config.PROMPT_ENUNCIADO.format(code1=code1, code2=code2)
            
            print(f"[{i+1}/{len(problems)}] Processing {curso}/{asignacion}/{tarea}...", end=" ")
            sys.stdout.flush()
            
            try:
                response = provider.generate(prompt)
                enunciado, lenguaje = parse_llm_response(response)
            except Exception as e:
                print(f"Error: {e}")
                continue
            
            writer.writerow([curso, asignacion, tarea, enunciado, lenguaje])
            f.flush()
            
            print(f"OK - {enunciado[:50]}...")
    
    print(f"\nCompletado! Enunciados guardados en {args.output}")


if __name__ == "__main__":
    main()