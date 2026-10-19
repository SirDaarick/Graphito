import os
import json

def generar_entregables():
    extensiones_validas = {".c": "c", ".cpp": "cpp"}
    
    # ---- 
    directorio_raiz = os.getcwd() 
    ejercicios_json = []
    estructura_md = {}

    for raiz, carpetas, archivos in os.walk(directorio_raiz):
        # Ignorar carpetas ocultas
        if ".git" in raiz:
            continue
            
        for archivo in sorted(archivos):
            nombre, ext = os.path.splitext(archivo)
            
            if ext in extensiones_validas:
                ruta_completa = os.path.join(raiz, archivo)
                # Obtener  ruta relativa
                ruta_relativa = os.path.relpath(ruta_completa, directorio_raiz)
                partes_ruta = ruta_relativa.split(os.sep)
                
                # DMateria
                materia = partes_ruta[0] if len(partes_ruta) > 1 else "Raiz"
                
                # Unidad
                unidad = "Sin Unidad"
                for parte in partes_ruta:
                    if "Unidad" in parte or "unidad" in parte.lower():
                        unidad = parte
                        break
                
                # Leer el codigo fuente
                try:
                    with open(ruta_completa, "r", encoding="utf-8") as f:
                        codigo = f.read()
                except UnicodeDecodeError:
                    with open(ruta_completa, "r", encoding="latin-1") as f:
                        codigo = f.read()
                
                lenguaje = extensiones_validas[ext]
                ruta_limpia = ruta_relativa.replace("\\", "/") # Para compatibilidad cruzada
                
                # --- Agregar al arreglo para el JSON ---
                ejercicios_json.append({
                    "materia": materia,
                    "unidad": unidad,
                    "nombre_archivo": archivo,
                    "ruta_original": ruta_limpia,
                    "lenguaje": lenguaje,
                    "codigo": codigo
                })
                
                # --- Agrupar para el Markdown ---
                if materia not in estructura_md:
                    estructura_md[materia] = {}
                if unidad not in estructura_md[materia]:
                    estructura_md[materia][unidad] = []
                    
                estructura_md[materia][unidad].append({
                    "archivo": archivo,
                    "ruta": ruta_limpia,
                    "lenguaje": lenguaje,
                    "codigo": codigo
                })

    
    with open("Entregable_Ejercicios.json", "w", encoding="utf-8") as f_json:
        json.dump(ejercicios_json, f_json, indent=4, ensure_ascii=False)
    print("Se genero exitosamente: Entregable_Ejercicios.json")

  
    with open("Entregable_Ejercicios.md", "w", encoding="utf-8") as f_md:
        f_md.write("# Repositorio General de Programas ESCOM\n\n")
        f_md.write(f"**Total de ejercicios compilados:** {len(ejercicios_json)}\n\n")
        f_md.write("---\n\n")
        
        for materia, unidades in estructura_md.items():
            f_md.write(f"## Materia: {materia.replace('_', ' ').upper()}\n\n")
            
            for unidad, lista_archivos in unidades.items():
                f_md.write(f"### Carpeta: {unidad}\n\n")
                
                for obj in lista_archivos:
                    f_md.write(f"#### Archivo: `{obj['archivo']}`\n")
                    f_md.write(f"- **Ruta en carpeta:** `{obj['ruta']}`\n\n")
                    f_md.write(f"```{obj['lenguaje']}\n")
                    f_md.write(obj["codigo"].rstrip() + "\n")
                    f_md.write("```\n\n")
                    
            f_md.write("---\n\n")
            
    print("Se genero exitosamente: Entregable_Ejercicios.md")

if __name__ == "__main__":
    generar_entregables()