# Recorta Facil

Recorta Facil e um aplicativo simples para remover fundo de imagens, revisar o
resultado manualmente e salvar PNG com transparencia.

O projeto nasceu para um fluxo bem pratico: usar a API remove.bg quando precisa
de recorte mais preciso, e depois corrigir sobras com uma borracha manual dentro
do proprio app.

## Funcionalidades

- Interface grafica em Tkinter.
- Remocao de fundo via API remove.bg.
- Remocao local para fundos simples, solidos ou xadrez.
- Editor manual com pincel para apagar sobras do fundo.
- Ferramenta para restaurar partes apagadas por engano.
- Preview antes de salvar.
- Processamento em lote por pasta.
- Melhoria leve de nitidez e cor.
- Upscale simples em 1.5x ou 2x.
- Saida transparente, branca ou preta.
- Uso por terminal para automatizar tarefas.

## Requisitos

- Python 3.10 ou superior.
- Windows, macOS ou Linux com Tkinter disponivel.
- Chave da API remove.bg para o modo `api`.

## Instalar

Clone o repositorio e instale as dependencias:

```bat
git clone https://github.com/tomaziu/recorta-facil.git
cd recorta-facil
python -m pip install -r requirements.txt
```

No Windows, voce tambem pode abrir o app com duplo clique em:

```bat
run-background-remover.bat
```

Ou iniciar pelo terminal:

```bat
python background_remover.py --gui
```

## Configurar a API

Crie uma chave em https://www.remove.bg/api e configure a variavel de ambiente:

```bat
setx REMOVE_BG_API_KEY "SUA_CHAVE_AQUI"
```

Feche e abra o terminal/app de novo. Depois use o modo `auto` ou `api`.

Tambem da para passar a chave direto no comando:

```bat
python background_remover.py "foto.jpg" --mode api --api-key "SUA_CHAVE_AQUI" -o "foto-sem-fundo.png"
```

Observacao: a API remove.bg pode consumir creditos da sua conta.

## Usar Pela Interface

1. Abra `run-background-remover.bat` ou rode `python background_remover.py --gui`.
2. Clique em `Escolher` e selecione uma imagem.
3. Em `Modo`, escolha `api` para melhor qualidade ou `auto`.
4. Clique em `Previsualizar`.
5. Se precisar ajustar, clique em `Editar manualmente`.
6. Clique em `Aplicar` na janela de edicao.
7. Clique em `Salvar PNG`.

## Ajuste Manual

Depois de clicar em `Previsualizar`, clique em `Editar manualmente`.

Na janela de edicao:

- `Apagar`: remove manualmente partes que sobraram.
- `Restaurar`: recupera partes apagadas por engano.
- `Pincel`: muda o tamanho da borracha.
- `Desfazer`: volta a ultima pincelada.
- `Aplicar`: manda a edicao de volta para a tela principal.

Depois clique em `Salvar PNG`.

## Usar Pelo Terminal

Remover o fundo de uma imagem:

```bat
python background_remover.py "foto.jpg" -o "foto-sem-fundo.png"
```

Usar a API remove.bg:

```bat
python background_remover.py "foto.jpg" --mode api -o "foto-sem-fundo.png"
```

Processar uma pasta inteira:

```bat
python background_remover.py --batch "C:\caminho\imagens" --out-dir "C:\caminho\sem-fundo"
```

## Modos

- `auto`: usa a API remove.bg quando existe chave, depois tenta AI local/rembg,
  depois remocao local.
- `api`: usa remove.bg, normalmente o recorte mais preciso para fundos dificeis.
- `ai`: usa `rembg` local, se instalado.
- `border`: remove fundo parecido com a cor das bordas.
- `checker`: remove fundo xadrez claro, comum em previews de transparencia.

## AI Local Opcional

Para uma IA local, instale o removedor `rembg`:

```bat
python -m pip install rembg
```

Depois use o modo `auto` ou `ai`. Se o Python instalado nao aceitar `rembg`, o
app continua funcionando nos modos `api`, `border` e `checker`.

## Testes

Os testes principais usam `unittest`, sem precisar chamar a API:

```bat
python -m unittest discover -s tests
```

Se preferir `pytest`, instale as dependencias de desenvolvimento:

```bat
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Variaveis De Ambiente

Copie `.env.example` para `.env` se quiser guardar configuracoes locais:

```bat
copy .env.example .env
```

Nunca envie sua chave real da API para o GitHub.

## Limitacoes Conhecidas

- O modo `api` depende da remove.bg e pode consumir creditos.
- O modo local funciona melhor com fundos simples ou xadrez.
- O editor manual altera o alpha do PNG, mas ainda nao tem zoom/pan avancado.

## Contribuindo

Sugestoes, bugs e melhorias sao bem-vindos. Antes de abrir um pull request:

1. Rode os testes.
2. Evite commitar imagens geradas ou chaves de API.
3. Atualize o README ou CHANGELOG quando a mudanca afetar o uso do app.

## Licenca

Este projeto usa a licenca MIT. Veja [LICENSE](LICENSE).
