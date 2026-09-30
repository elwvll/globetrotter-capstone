"""Run all 5 services without Docker (for quick local tests).
Usage (from the microservices folder):  python run_all.py
Stop everything with Ctrl+C."""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
PORTS = {"auth": 5001, "destinations": 5002, "itineraries": 5003, "chat": 5004, "gateway": 5000}
procs = []
try:
    for name, port in PORTS.items():
        env = dict(os.environ, PORT=str(port))
        procs.append(subprocess.Popen([sys.executable, "app.py"], cwd=os.path.join(ROOT, name), env=env))
        print(f"started {name} on port {port}")
    print("\nOpen http://127.0.0.1:5000  (Ctrl+C to stop all)")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        p.terminate()
