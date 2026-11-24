# Otimizador de PC

App Windows (Python + CustomTkinter) de diagnóstico e ajustes seguros para PC gamer. Projeto de portfólio, interface e textos em **português (pt-BR)**.

## Comandos

```powershell
.\.venv\Scripts\python.exe -m otimizador --sem-admin   # roda sem UAC (só diagnóstico)
.\.venv\Scripts\python.exe -m pytest -q                 # testes
.\.venv\Scripts\python.exe tools\capturar_telas.py      # refaz os prints de docs/screenshots
.\build.ps1                                             # testes + dist\OtimizadorPC.exe
```

## Arquitetura

- `diagnostico/` só lê. `coleta.py` busca dados brutos; `hardware.py`/`sistema.py` são **funções puras** que interpretam (testáveis com JSON em `tests/dados/`).
- `ajustes/`: cada ajuste herda `Ajuste` (`base.py`) e implementa `status()`, `_aplicar()` e `_desfazer()`. Registrar em `criar_ajustes()` (`ajustes/__init__.py`).
- `ui/` não executa comandos do Windows diretamente; trabalho lento vai por `Executor` (`ui/tarefas.py`), porque o Tkinter não é thread-safe.
- `core/shell.py`: todo PowerShell passa por `powershell()`/`powershell_json()` (5.1, `-EncodedCommand`, saída UTF-8, `CREATE_NO_WINDOW`).

## Regras do projeto

- **Só ajustes seguros, documentados e reversíveis.** Nada de desativar serviços, tweaks de rede/registro, debloat. Explicações honestas sobre o ganho real.
- Nada é aplicado automaticamente; ajustes que alteram o sistema (`altera_sistema=True`) passam pelo ponto de restauração.
- `Estado.guardar_original()` guarda só o **primeiro** valor (para o Desfazer voltar ao estado original).
- Independente de hardware: identificar planos de energia por GUID, não por nome; não assumir Intel/NVIDIA.
- Privacidade: a UI e os prints nunca mostram caminhos completos com o nome do usuário; dados de teste sem SID/usuário/nome do PC.

## Armadilhas conhecidas

- `Win32_PowerPlan` exige admin → usar `powercfg /list`.
- Estado do HAGS vem do driver (`core/d3dkmt.py`); a chave `HwSchMode` muitas vezes não existe.
- Um `CTkFrame` vazio ocupa 200 px de altura → usar `grid_remove()` quando não houver conteúdo.
- `build.ps1` precisa ser salvo em **UTF-8 com BOM** (PowerShell 5.1) e usa `ErrorActionPreference = 'Continue'` (stderr do PyInstaller não é erro).
- O `.exe` tem `--uac-admin`: não dá para testá-lo sem aprovar o UAC. Para testar o pacote, gerar uma cópia sem `--uac-admin` e rodar com `--sem-admin`.
- Fluxos que exigem admin (ponto de restauração, ReTrim, HAGS, `C:\Windows\Temp`) só podem ser validados pelo usuário rodando elevado.

## Publicação

Repositório: https://github.com/Luisinho13/otimizador-pc. O `.exe` vai em **Releases** (`gh release create vX.Y.Z dist\OtimizadorPC.exe`), nunca no repositório. Ao mudar a versão, atualizar `otimizador/__init__.py` e `tools/versao.txt`.
