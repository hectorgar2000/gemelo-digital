@echo off
:: Ejecutar como Administrador
:: Bloquea acceso externo a InfluxDB (8086) y Grafana (3000)
:: Solo permite conexiones desde localhost (127.0.0.1)

echo Aplicando reglas de firewall para Gemelo Digital...

netsh advfirewall firewall add rule ^
  name="GemeloDigital - InfluxDB solo localhost" ^
  protocol=TCP dir=in localport=8086 remoteip=127.0.0.1 action=allow

netsh advfirewall firewall add rule ^
  name="GemeloDigital - InfluxDB bloquear externo" ^
  protocol=TCP dir=in localport=8086 remoteip=LocalSubnet action=block

netsh advfirewall firewall add rule ^
  name="GemeloDigital - Grafana solo localhost" ^
  protocol=TCP dir=in localport=3000 remoteip=127.0.0.1 action=allow

netsh advfirewall firewall add rule ^
  name="GemeloDigital - Grafana bloquear externo" ^
  protocol=TCP dir=in localport=3000 remoteip=LocalSubnet action=block

echo.
echo [OK] Reglas aplicadas. Verifica en: Panel de Control > Firewall > Reglas de entrada
echo      Busca "GemeloDigital" para ver las 4 reglas creadas.
pause
