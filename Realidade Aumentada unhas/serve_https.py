import http.server, ssl, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = 8443

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(certfile="cert.pem", keyfile="key.pem")

class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".wasm": "application/wasm",
        ".svg": "image/svg+xml",
    }

httpd = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

print(f"Servidor HTTPS rodando:")
print(f"  Neste PC:   https://localhost:{PORT}")
print(f"  No celular: https://SEU-IP:{PORT}  (descubra o IP com ipconfig)")
print("Atencao: certificado autoassinado -> o navegador mostra aviso.")
print("Clique em 'Avancado' > 'Continuar para o site'.")
httpd.serve_forever()
