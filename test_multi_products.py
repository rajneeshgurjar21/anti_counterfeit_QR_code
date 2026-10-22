import urllib.request
import json

def api_post(endpoint, data):
    req = urllib.request.Request(
        f'http://localhost:8080{endpoint}',
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode('utf-8'))

# 1. Register Product A (PROD-201)
print("1. Registering Product A (PROD-201)...")
api_post('/api/generate', {
    'serial_no': 'PROD-201',
    'product_name': 'Medicine A',
    'brand_name': 'Brand Alpha',
    'batch_no': 'BATCH-01',
    'payload': 'https://brand-auth.com/verify?id=PROD-201&batch=01'
})

# 2. Register Product B (PROD-202)
print("2. Registering Product B (PROD-202)...")
api_post('/api/generate', {
    'serial_no': 'PROD-202',
    'product_name': 'Medicine B',
    'brand_name': 'Brand Alpha',
    'batch_no': 'BATCH-02',
    'payload': 'https://brand-auth.com/verify?id=PROD-202&batch=02'
})

# 3. Simulate scan on Product A
resA1 = api_post('/api/simulate', {
    'type': 'genuine',
    'serial_no': 'PROD-201',
    'payload': 'https://brand-auth.com/verify?id=PROD-201&batch=01'
})
print("Scan 1 on Product A (PROD-201) -> Count:", resA1['product_info']['scan_count'])

# 4. Simulate scan on Product B
resB1 = api_post('/api/simulate', {
    'type': 'genuine',
    'serial_no': 'PROD-202',
    'payload': 'https://brand-auth.com/verify?id=PROD-202&batch=02'
})
print("Scan 1 on Product B (PROD-202) -> Count:", resB1['product_info']['scan_count'])

# 5. Simulate 2nd scan on Product A
resA2 = api_post('/api/simulate', {
    'type': 'genuine',
    'serial_no': 'PROD-201',
    'payload': 'https://brand-auth.com/verify?id=PROD-201&batch=01'
})
print("Scan 2 on Product A (PROD-201) -> Count:", resA2['product_info']['scan_count'], f"({resA2['product_info']['clone_message']})")

# 6. Check Product B count again (must still be 1!)
res_check = urllib.request.urlopen('http://localhost:8080/api/products')
prods = json.loads(res_check.read().decode('utf-8'))
pB = next(p for p in prods if p['serial_no'] == 'PROD-202')
print("Final Product B (PROD-202) Count in DB:", pB['scan_count'], "(Must be 1!)")
