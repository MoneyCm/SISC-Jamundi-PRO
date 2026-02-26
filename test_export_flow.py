import requests, json, os, time

BASE = 'http://localhost:8000/api/intelligence'

def test_report(report_id):
    # 1. POST export/pdf
    post_resp = requests.post(f'{BASE}/reports/{report_id}/export/pdf')
    print(f'POST /reports/{report_id}/export/pdf ->', post_resp.status_code)
    if post_resp.status_code != 200:
        print('Error response:', post_resp.text)
        return None
    data = post_resp.json()
    link = data.get('download_link')
    print('download_link:', link)
    # 2. GET PDF
    get_resp = requests.get(link)
    print('First GET ->', get_resp.status_code)
    # Save to /tmp for verification
    if get_resp.status_code == 200:
        open(f'/tmp/report_{report_id}.pdf','wb').write(get_resp.content)
    # 3. Re‑attempt GET (should fail)
    retry_resp = requests.get(link)
    print('Retry GET ->', retry_resp.status_code, retry_resp.text[:200])
    return link

if __name__ == '__main__':
    weekly_link = test_report(1)  # semanal 2026-W08
    monthly_link = test_report(2)  # mensual 2026-M02
    # Wait a moment before exiting
    time.sleep(1)
