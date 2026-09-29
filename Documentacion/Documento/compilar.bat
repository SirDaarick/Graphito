@echo off
cd /d "%~dp0"
echo Compilando documento LaTeX con Tectonic...
tectonic main.tex
if %ERRORLEVEL% equ 0 (
    echo Compilacion exitosa: main.pdf generado.
) else (
    echo Error durante la compilacion.
)
pause
