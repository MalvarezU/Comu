from servidores_cli.commands.dns import _dig_ok

DIG_OK = """; <<>> DiG 9.x <<>> @192.168.1.10 www.midominio.com
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
;; ANSWER SECTION:
www.midominio.com.    604800    IN    A    192.168.1.12

;; Query time: 0 msec
"""

DIG_SERVFAIL = """;; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 1
;; ANSWER SECTION:
"""

DIG_VACIO = """;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
;; ANSWER SECTION:
;; Query time: 0 msec
"""


def test_noerror_con_respuesta():
    assert _dig_ok(DIG_OK) is True


def test_servfail():
    assert _dig_ok(DIG_SERVFAIL) is False


def test_noerror_sin_respuestas():
    assert _dig_ok(DIG_VACIO) is False


def test_sin_status():
    assert _dig_ok("salida sin cabecera dig") is False
