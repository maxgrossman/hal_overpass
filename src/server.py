from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import parse
from os import environ, path
from string import Template
from threading import Thread
from json import dumps
from base64 import b64encode, b64decode
from hal import get_overpass_data
from cache import FileCache

HOST = environ.get('HAL_HOST', 'localhost')
PORT = int(environ.get('HAL_PORT', 8080))
BASE_PATH = environ.get('HAL_BASEPATH', None)

if BASE_PATH == "":
    BASE_PATH = None

if BASE_PATH is not None and BASE_PATH[0] != '/':
    raise Exception(f"HAL_BASEPATH={BASE_PATH}. It must begin with the '/' char.")

INDEX_HTML = Template("""
<body>
     <form action="$base_path/ask" method="post">
        <label for="question">Ask you shall receive data:</label><br>
        <input type="text" id="question" name="question"><br>
        <input type="submit" value="Submit">
    </form>
</body>
""")
ASK_HTML =  Template("""
<body>
    <div id="cache_data">$cache_data_html</div>
    <script>
        const question_id = "$question_id"
        const cache_data_json = $cache_data_json
        const formatter_funcs = {
            'form_data': function (key, form_data) {
                return form_data.split("&").map(function(f) {
                    return f.replaceAll('+',' ').replace("=", ": ")
                }).join('\\n')
            }
        }

        function format_key_pair(key, data) {
            return key + ": " + data
        }

        window.onload = function() {
            let answered = cache_data_json.status === 'answered'
            if (!answered) {
                async function get_status() {
                    let ask = await fetch('$base_path/ask/' + question_id, {'method':'post'})
                    if (ask.status === 200) {
                        let ask_map = await ask.json()
                        for (const key of Object.keys(ask_map)) {
                            cache_data_json[key] = ask_map[key]
                        }

                        if (cache_data_json.status === 'asking') {
                            await new Promise(resolve => setTimeout(resolve, 1000))
                            await get_status()
                        } else {
                            for (key of Object.keys(cache_data_json)) {
                                const formatter_func = formatter_funcs[key] || format_key_pair;
                                document.querySelector('#' + key).innerText =
                                    formatter_func(key, cache_data_json[key])
                            }
                            document.querySelector('#status').innerText =
                                'Status: ' + ask_map.status
                        }
                    }
                }
                get_status()
            }
        }
    </script>
<body>
""")



def build_path(path):
    if path[0] != '/':
        path = f"/{path}"

    if BASE_PATH is not None:
        path = f"{BASE_PATH}{path}"
    return path


ASKS_MAP = FileCache('cache.json')

def form_to_map(form_data):
    form_data_map = {}
    for form_input in form_data.split('&'):
        (input_key, input_value) = form_input.split('=')
        form_data_map[input_key] = input_value

    return form_data_map

def form_data_to_question_id(form_data):
    return b64encode(form_data.encode('utf-8')).decode('utf-8')
def question_id_to_form_data(question_id):
    return b64decode(question_id.encode('utf-8')).decode('utf-8')

def threaded_ask(question_id, form_data_map):
    hal_response = get_overpass_data(form_data_map['question'])

    question_id_cache = ASKS_MAP.get(question_id)
    question_id_cache['status'] =  'failed to answer' if not hal_response else 'answered'

    for key in hal_response:
        question_id_cache[key] = hal_response[key]

    ASKS_MAP.set(question_id, question_id_cache)


def format_key_pair(key, data):
    return f"{key}: {data}"
def format_code_snippet(key, data):
    return f"{key}:<br/><code>{data}</code>"
def format_file_link(key, data):
    return f"{key}: <a target=\"_blank\" href=\"{build_path(data)}\">{data.split('/')[1]}</a>"
def format_form_data(key, form_data):
    return ", ".join([": ".join(f.split("=")).replace('+', ' ') for f in form_data.split("&")])

FORMAT_FUNCS = {
    'form_data': format_form_data,
    'overpass_query': format_code_snippet,
    'data_file_name': format_file_link,
    'query_file_name': format_file_link,
}

def build_cache_data_html(question_id):
    cache_data = ASKS_MAP.get(question_id)
    cache_html = ''
    for key in cache_data:
        format_func = FORMAT_FUNCS[key] if key in FORMAT_FUNCS else format_key_pair
        cache_html += f"<div id={key}>{format_func(key, cache_data[key])}</div>"
    return cache_html

class ServerHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.routes_map = {
            "": {
                "GET": self.default_get
            },
            "ask": {
                "GET": self.ask_get,
                "POST": self.ask_post
            },
            "results": {
                "GET": self.results_get
            },
            "ping": {
                "GET": self.ping_get
            }
        }
        super().__init__(*args, **kwargs)

    def not_found_response(self):
        self.send_response(404)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write('{"status": "Not found"}'.encode('utf-8'))

    def default_get(self, parsed_path_parts):
        self.send_response(200)
        self.send_header('Content-Type',
                'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(INDEX_HTML.substitute({
            "base_path": BASE_PATH if BASE_PATH is not None else ""
        }).encode('utf-8'))

    def ask_get(self, parsed_path_parts):
        if len(parsed_path_parts) == 1:
            self.not_found_response();
            return;

        question_id = parsed_path_parts[1]

        self.send_response(200)
        self.send_header('Content-Type',
            'text/html; charset=utf-8')
        self.end_headers()

        ask_cache = ASKS_MAP.get(question_id).copy()
        for key in ['data_file_name', 'query_file_name']:
            if key in ask_cache:
                ask_cache[key] = build_path(ask_cache[key])

        formatted_html = ASK_HTML.substitute({
            "base_path": BASE_PATH if BASE_PATH is not None else "",
            "question_id": question_id,
            "cache_data_json": dumps(ask_cache),
            "cache_data_html": build_cache_data_html(question_id)
        }).encode('utf-8')

        self.wfile.write(formatted_html)

    def ask_post(self, parsed_path_parts):
        num_path_parts = len(parsed_path_parts)
        if num_path_parts == 1:
            form_data = bytes.decode(self.rfile.read(int(
                self.headers['Content-Length'])))

            question_id = form_data_to_question_id(form_data)

            if not ASKS_MAP.has(question_id):
                ASKS_MAP.set(question_id, {'status': 'asking', 'form_data': form_data})
                ask_thread = Thread(target=threaded_ask, args=(question_id, form_to_map(form_data)))
                ask_thread.start()

            self.send_response(302)
            self.send_header('location', build_path(f'/ask/{question_id}'))
            self.end_headers()
        elif num_path_parts == 2:
            question_id = parsed_path_parts[1]

            if not ASKS_MAP.has(question_id):
                self.not_found_response();
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(dumps(ASKS_MAP.get(question_id)).encode('utf-8'))

    def results_get(self, parsed_path_parts):
        file_path = parse.unquote(path.join(*parsed_path_parts))
        if path.exists(file_path):
            self.send_response(200)
            self.send_header('Content-Type',
                'text/html; charset=utf-8')
            self.end_headers()

            with open(file_path, 'r+') as f:
                self.wfile.write(f.read().encode('utf-8'))

    def ping_get(self, parsed_path_parts):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write('{"status": "OK"}'.encode('utf-8'))

    def parse_path(self, path):
        # remove BASE_PATH string if it exists
        if BASE_PATH is not None:
            path = path[len(BASE_PATH):]

        # remove the leading '/' char
        return path[1:].split('/')

    def do_METHOD(self, method):
        path = parse.urlparse(self.path).path

        if BASE_PATH is not None and path.find(BASE_PATH) == -1:
            self.not_found_response();
            return

        parsed_path_parts = self.parse_path(path)
        route_map = self.routes_map.get(parsed_path_parts[0], {})
        route_method = route_map.get(method, None)

        if route_method is None:
            self.send_response(404)
        else:
            route_method(parsed_path_parts)

    def do_GET(self):
        self.do_METHOD('GET')
    def do_POST(self):
        self.do_METHOD('POST')

if __name__ == '__main__':
    server = HTTPServer((HOST, PORT), ServerHandler)
    print(f'Server runing at http://{HOST}:{PORT}')
    server.serve_forever()
