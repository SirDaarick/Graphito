#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import config


def count_problems_in_dataset(dataset_path: Path) -> dict:
    counts = defaultdict(lambda: {"problemas": set(), "total": 0})
    
    for curso_dir in dataset_path.iterdir():
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
                
                key = f"{curso}/{asignacion}/{tarea_dir.name}"
                counts[f"{curso}/{asignacion}"]["problemas"].add(key)
                counts[f"{curso}/{asignacion}"]["total"] += 1
    
    return dict(counts)


def scan_dataset(base_path: Path) -> dict[tuple, dict]:
    problemas = {}
    
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
                
                code_files = list(tarea_dir.glob("*.c")) + list(tarea_dir.glob("*.cpp"))
                
                problemas[(curso, asignacion, tarea)] = {
                    "curso": curso,
                    "carpeta": asignacion,
                    "subcarpeta": tarea,
                    "num_archivos": len(code_files)
                }
    
    return problemas


def scan_output(output_path: Path) -> dict[tuple, dict]:
    referencias = defaultdict(lambda: {"modelos": defaultdict(int), "total": 0})
    
    if not output_path.exists():
        return referencias
    
    for curso_dir in output_path.iterdir():
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
                
                key = (curso, asignacion, tarea)
                
                for ref_file in tarea_dir.glob("referencia_*.c"):
                    if ref_file.stem == "metadata":
                        continue
                    
                    parts = ref_file.stem.replace("referencia_v", "").split("_")
                    if len(parts) >= 2:
                        modelo = parts[-1]
                        referencias[key]["modelos"][modelo] += 1
                        referencias[key]["total"] += 1
    
    return referencias


def print_stats(dataset_problems: dict, referencias: dict, verbose: bool = False):
    aggregated = defaultdict(lambda: {"problemas": 0, "referencias": 0})
    
    for (curso, carpeta, subcarpeta), data in dataset_problems.items():
        key = f"{curso}/{carpeta}"
        aggregated[key]["problemas"] += 1
    
    for (curso, carpeta, subcarpeta), data in referencias.items():
        key = f"{curso}/{carpeta}"
        aggregated[key]["referencias"] += data["total"]
    
    print("\n" + "=" * 70)
    print("ESTADÍSTICAS DEL DATASET IEEE PLAGIARISM")
    print("=" * 70)
    print(f"\n{'Curso/Asignación':<20} {'Problemas':<12} {'Referencias IA':<15}")
    print("-" * 50)
    
    total_problemas = 0
    total_referencias = 0
    
    for key in sorted(aggregated.keys()):
        total_problemas += aggregated[key]["problemas"]
        total_referencias += aggregated[key]["referencias"]
        print(f"{key:<20} {aggregated[key]['problemas']:<12} {aggregated[key]['referencias']:<15}")
    
    print("-" * 50)
    print(f"{'TOTAL':<20} {total_problemas:<12} {total_referencias:<15}")
    print("=" * 70)
    
    print(f"\n📊 Resumen:")
    print(f"   - Total de problemas únicos: {len(dataset_problems)}")
    print(f"   - Total de referencias IA generadas: {sum(r['total'] for r in referencias.values())}")
    
    if verbose and referencias:
        print("\n📋 Detalle por problema:")
        print("-" * 70)
        
        for (curso, carpeta, subcarpeta), data in sorted(dataset_problems.items()):
            key = (curso, carpeta, subcarpeta)
            ref_data = referencias.get(key, {"modelos": {}, "total": 0})
            
            print(f"\n{curso}/{carpeta}/{subcarpeta}")
            print(f"   Originales: {data['num_archivos']}")
            print(f"   IA Generadas: {ref_data['total']}")
            
            if ref_data["modelos"]:
                print("   Por modelo:")
                for modelo, count in ref_data["modelos"].items():
                    print(f"      - {modelo}: {count}")


def export_csv(dataset_problems: dict, referencias: dict, output_path: Path):
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["curso", "carpeta", "subcarpeta", "archivos_originales", "referencias_ia"])
        
        for (curso, carpeta, subcarpeta), data in sorted(dataset_problems.items()):
            key = (curso, carpeta, subcarpeta)
            ref_data = referencias.get(key, {"total": 0})
            
            writer.writerow([
                curso,
                carpeta,
                subcarpeta,
                data["num_archivos"],
                ref_data["total"]
            ])
    
    print(f"CSV exportado a: {output_path}")


def export_json(dataset_problems: dict, referencias: dict, output_path: Path):
    result = {
        "dataset": {
            "total_problemas": len(dataset_problems),
            "problemas": []
        },
        "referencias": {
            "total": sum(r["total"] for r in referencias.values()),
            "por_problema": []
        }
    }
    
    for (curso, carpeta, subcarpeta), data in sorted(dataset_problems.items()):
        key = (curso, carpeta, subcarpeta)
        ref_data = referencias.get(key, {"modelos": {}, "total": 0})
        
        result["dataset"]["problemas"].append({
            "curso": curso,
            "carpeta": carpeta,
            "subcarpeta": subcarpeta,
            "archivos_originales": data["num_archivos"]
        })
        
        if ref_data["total"] > 0:
            result["referencias"]["por_problema"].append({
                "asignacion": f"{curso}/{carpeta}/{subcarpeta}",
                "total": ref_data["total"],
                "por_modelo": dict(ref_data["modelos"])
            })
    
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON exportado a: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Estadísticas del dataset y referencias generadas"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar detalle por problema"
    )
    parser.add_argument(
        "--csv",
        metavar="ARCHIVO",
        help="Exportar a CSV"
    )
    parser.add_argument(
        "--json",
        metavar="ARCHIVO",
        help="Exportar a JSON"
    )
    parser.add_argument(
        "--dataset-path",
        default=str(config.DATASET_PATH),
        help="Ruta del dataset"
    )
    parser.add_argument(
        "--output-path",
        default=str(config.OUTPUT_PATH),
        help="Ruta de salida de referencias"
    )
    
    args = parser.parse_args()
    
    dataset_problems = scan_dataset(Path(args.dataset_path))
    referencias = scan_output(Path(args.output_path))
    
    print(f"Dataset: {args.dataset_path}")
    print(f"  Problemas encontrados: {len(dataset_problems)}")
    print(f"Referencias: {args.output_path}")
    print(f"  Referencias encontradas: {sum(r['total'] for r in referencias.values())}")
    
    print_stats(dataset_problems, referencias, verbose=args.verbose)
    
    if args.csv:
        export_csv(dataset_problems, referencias, Path(args.csv))
    
    if args.json:
        export_json(dataset_problems, referencias, Path(args.json))


if __name__ == "__main__":
    main()