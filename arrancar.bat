@echo off
echo Arrancando Gemelo Digital...

REM InfluxDB
tasklist /FI "IMAGENAME eq influxd.exe" 2>NUL | find /I "influxd.exe" >NUL
if errorlevel 1 (
    start "InfluxDB" /MIN "C:\Users\Admin\influxdb2\influxd.exe"
    echo [OK] InfluxDB arrancado
) else (
    echo [--] InfluxDB ya estaba corriendo
)

REM Grafana (instalado como servicio Windows — arranca automaticamente)
sc query Grafana | find "RUNNING" >NUL 2>&1
if errorlevel 1 (
    net start Grafana >NUL 2>&1
    echo [OK] Grafana arrancado
) else (
    echo [--] Grafana ya estaba corriendo
)

REM Web app Next.js
tasklist /FI "IMAGENAME eq node.exe" 2>NUL | find /I "node.exe" >NUL
if errorlevel 1 (
    start "Web App" /MIN cmd /c "cd /d C:\Users\Admin\Desktop\gemelo_digital\web && npm run dev"
    echo [OK] Web app arrancada
) else (
    echo [--] Web app ya estaba corriendo
)

REM Colector de datos
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if errorlevel 1 (
    start "Colector" /MIN "C:\Users\Admin\Desktop\gemelo_digital\venv\Scripts\python.exe" "C:\Users\Admin\Desktop\gemelo_digital\collector.py"
    echo [OK] Colector arrancado
) else (
    echo [--] Colector ya estaba corriendo
)

timeout /t 6 /nobreak >NUL
echo.
echo Servicios disponibles en:
echo   InfluxDB:  http://localhost:8086
echo   Grafana:   http://localhost:3000
echo   Web app:   http://localhost:3001
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >NUL
