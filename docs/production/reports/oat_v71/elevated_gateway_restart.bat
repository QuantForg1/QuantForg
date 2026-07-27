@echo off
set LOG=C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\elevated_restart.txt
echo [%DATE% %TIME%] begin> "%LOG%"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765 ^| findstr LISTENING') do (
  echo killing %%a>> "%LOG%"
  taskkill /F /PID %%a >> "%LOG%" 2>&1
)
timeout /t 4 /nobreak >nul
cd /d "C:\Users\P7 PROVIDER\QuantForg"
echo starting gateway>> "%LOG%"
start "" /B "C:\Python314\python.exe" -m services.mt5_gateway.main > "C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\gateway_elevated.out.log" 2> "C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\gateway_elevated.err.log"
timeout /t 8 /nobreak >nul
powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:8765/health | ConvertTo-Json -Depth 8 | Set-Content 'C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\step3_gateway_after_elevated.json' } catch { $_ | Out-File 'C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\step3_gateway_after_elevated.json' }"
echo done> "C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\elevated_done.txt"
echo [%DATE% %TIME%] done>> "%LOG%"
