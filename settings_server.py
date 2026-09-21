"""Standalone settings server for agent.conf.

Run: python3 settings_server.py
Serves http://127.0.0.1:8790/
"""

import html
import http.server
import os
import urllib.parse

import agent_conf

HOST = "127.0.0.1"
PORT = 8790

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONF = os.path.join(_HERE, "agent.conf")
DEFAULT_HTML = os.path.join(_HERE, "settings.html")


def _read_html(html_path):
    with open(html_path, "r") as fh:
        return fh.read()


def _row(key, value, errors):
    escaped_value = html.escape(str(value), quote=True)
    error = errors.get(key)
    row_class = "row bad" if error else "row"
    err_html = ""
    if error:
        err_html = '\n        <div class="err">%s</div>' % html.escape(error, quote=True)
    return (
        '    <div class="%s">\n'
        '      <label for="%s">%s</label>\n'
        '      <div class="field">\n'
        '        <input id="%s" name="%s" value="%s">%s\n'
        "      </div>\n"
        '      <div class="hint">%s</div>\n'
        "    </div>"
    ) % (
        row_class,
        html.escape(key, quote=True),
        html.escape(key, quote=True),
        html.escape(key, quote=True),
        html.escape(key, quote=True),
        escaped_value,
        err_html,
        html.escape(agent_conf.hint_for(key), quote=True),
    )


def _rows_for_group(conf, group_name, errors):
    keys = [key for key in conf if agent_conf.group_of(key) == group_name]
    if group_name == "other" and not keys:
        return ""
    rows = "\n".join(_row(key, conf[key], errors) for key in keys)
    if group_name == "other":
        return '<h2>Other</h2>\n<div class="card">\n' + rows + "\n</div>"
    return rows


def _render(conf, errors, saved, html_path):
    page = _read_html(html_path)
    saved_html = '<div class="saved">Saved</div>' if saved else ""
    page = page.replace("<!--SAVED-->", saved_html)
    for group_name, _keys in agent_conf.GROUPS:
        page = page.replace(
            "<!--ROWS:%s-->" % group_name, _rows_for_group(conf, group_name, errors)
        )
    page = page.replace("<!--ROWS:other-->", _rows_for_group(conf, "other", errors))
    return page


def _make_handler(conf_path, html_path, quiet):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not quiet:
                http.server.BaseHTTPRequestHandler.log_message(self, fmt, *args)

        def _send_page(self, page):
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_404(self):
            body = b"Not Found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/":
                self._send_404()
                return
            conf = agent_conf.load(conf_path)
            page = _render(conf, {}, False, html_path)
            self._send_page(page)

        def do_POST(self):
            if self.path != "/save":
                self._send_404()
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            form = urllib.parse.parse_qs(body, keep_blank_values=True)

            conf = agent_conf.load(conf_path)
            new_conf = dict(conf)
            for key in conf:
                if key in form:
                    new_conf[key] = form[key][0]

            errors = agent_conf.validate(new_conf)
            if errors:
                page = _render(new_conf, errors, False, html_path)
            else:
                ordered = {key: new_conf[key] for key in conf}
                agent_conf.save(ordered, conf_path)
                page = _render(ordered, {}, True, html_path)
            self._send_page(page)

    return Handler


def make_server(port=PORT, conf_path=DEFAULT_CONF, html_path=DEFAULT_HTML, quiet=False):
    handler = _make_handler(conf_path, html_path, quiet)
    return http.server.HTTPServer((HOST, port), handler)


def main():
    srv = make_server()
    print("http://%s:%d/" % (HOST, srv.server_address[1]))
    srv.serve_forever()


if __name__ == "__main__":
    main()
