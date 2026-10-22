import urllib.request
import json

tests = ['genuine', 'blur_test', 'counterfeit']
for t in tests:
    payload_data = json.dumps({'type': t, 'serial_no': 'PROD-2026-X8879'}).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:8080/api/simulate', 
        data=payload_data, 
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req)
    d = json.loads(resp.read().decode('utf-8'))
    print(f"Button: {t:<12} -> Score: {d['authenticity_score']:5.1f}% | Verdict: {d['verdict']}")
