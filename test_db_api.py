import urllib.request
import json

# Test 1: Products DB list
resp = urllib.request.urlopen('http://localhost:8080/api/products')
prods = json.loads(resp.read().decode('utf-8'))
print('Registered products in DB:', len(prods))
for p in prods[:2]:
    print(' -', p['product_name'], '| Serial:', p['serial_no'], '| Batch:', p['batch_no'])

# Test 2: Simulate Genuine Scan
req = urllib.request.Request(
    'http://localhost:8080/api/simulate', 
    data=json.dumps({'type':'genuine', 'serial_no':'PROD-2026-X8879'}).encode('utf-8'), 
    headers={'Content-Type':'application/json'}
)
resp2 = urllib.request.urlopen(req)
d = json.loads(resp2.read().decode('utf-8'))
print('\nVerification Result:')
print('  Physical Status:', d['verdict'], f"({d['authenticity_score']}%)")
print('  Product Name:   ', d['product_info']['product_name'])
print('  Brand:          ', d['product_info']['brand_name'])
print('  Batch:          ', d['product_info']['batch_no'])
print('  Scan Count:     ', d['product_info']['scan_count'])
print('  Registry Status:', d['product_info']['db_status'])
print('  Alert Message:  ', d['product_info']['clone_message'])
