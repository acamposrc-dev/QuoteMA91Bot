from fastapi import FastAPI





app = FastAPI(title='MA91 - Bot', version='1.0')

@app.get('/health')
def health():
    return {
        "status": 'ok'
    }