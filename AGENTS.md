# Instrucoes Para IA

Este projeto e um app Python/Tkinter para remover fundo de imagens.

## Objetivo

Mantenha o app simples, local-first e facil de rodar no Windows. A API remove.bg
deve continuar opcional e configuravel por `REMOVE_BG_API_KEY` ou `--api-key`.

## Comandos Uteis

```bat
python -m pip install -r requirements.txt
python background_remover.py --gui
python -m unittest discover -s tests
python -m py_compile background_remover.py
```

## Cuidados

- Nao commite chaves de API, arquivos `.env` ou imagens geradas.
- Nao faca chamadas reais para a API em testes automatizados.
- Preserve o uso por interface e por terminal.
- Prefira dependencias pequenas. O app principal deve funcionar com Pillow e
  bibliotecas padrao do Python.
- Se alterar comportamento de CLI, atualize o README.
- Se adicionar uma funcionalidade visivel, atualize o CHANGELOG.

## Estrutura Atual

- `background_remover.py`: app, CLI e logica de processamento.
- `tests/`: testes automatizados.
- `run-background-remover.bat`: atalho para abrir a interface no Windows.
- `.env.example`: exemplo de variavel de ambiente da API.
