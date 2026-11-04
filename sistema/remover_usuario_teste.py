from datetime import datetime
from pathlib import Path
import sqlite3

pasta = Path(__file__).resolve().parent / "dados"
bancos = list(pasta.glob("*.db"))
login = "jhasjdhasdkj"

if not bancos:
    raise SystemExit("Nenhum banco encontrado.")

# Confere todos os bancos antes de alterar qualquer um.
for banco in bancos:
    with sqlite3.connect(banco) as conexao:
        eventos = conexao.execute(
            "SELECT origem, seq, tipo, chave FROM eventos"
        ).fetchall()

        if eventos != [("fvs", 1, "usuario", login)]:
            raise SystemExit(
                f"{banco.name} possui outros dados. Operacao cancelada."
            )

backup = pasta / f"backup-usuario-{datetime.now():%Y%m%d-%H%M%S}"
backup.mkdir()

for banco in bancos:
    with sqlite3.connect(banco) as conexao:
        conexao.execute(
            """
            DELETE FROM eventos
            WHERE origem = ? AND seq = ? AND tipo = ? AND chave = ?
            """,
            ("fvs", 1, "usuario", login),
        )

print(f"Usuario removido. Backup em: {backup}")