# Removedor de Fundo

Programa simples para remover fundo de imagens e salvar PNG transparente.

## Instalar

```bat
python -m pip install -r requirements.txt
```

## Abrir com interface

No Windows, de duplo clique em:

```bat
run-background-remover.bat
```

Ou rode pelo terminal:

```bat
python background_remover.py --gui
```

## Usar pelo terminal

Remover o fundo de uma imagem:

```bat
python background_remover.py "foto.jpg" -o "foto-sem-fundo.png"
```

Processar uma pasta inteira:

```bat
python background_remover.py --batch "C:\caminho\imagens" --out-dir "C:\caminho\sem-fundo"
```

## Modos

- `auto`: usa a API remove.bg quando existe chave, depois tenta AI local/rembg, depois remocao local.
- `api`: usa remove.bg, normalmente o recorte mais preciso para fundos dificeis.
- `ai`: usa `rembg` local, se instalado.
- `border`: remove fundo parecido com a cor das bordas.
- `checker`: remove fundo xadrez claro, comum em previews de transparencia.

## Extras

- Preview antes de salvar.
- Editor manual com pincel para apagar sobras do fundo.
- Ferramenta de restaurar e desfazer no editor manual.
- Processamento em lote.
- Bordas suaves.
- Melhoria de nitidez/cor.
- Aumento de tamanho em 1.5x ou 2x.
- Saida transparente, branca ou preta.

## AI opcional

## Ajuste manual

Depois de clicar em `Previsualizar`, clique em `Editar manualmente`.

Na janela de edicao:

- `Apagar`: remove manualmente partes que sobraram.
- `Restaurar`: recupera partes apagadas por engano.
- `Pincel`: muda o tamanho da borracha.
- `Desfazer`: volta a ultima pincelada.
- `Aplicar`: manda a edicao de volta para a tela principal.

Depois clique em `Salvar PNG`.

### Opcao mais precisa: remove.bg API

Crie uma chave em https://www.remove.bg/api e configure no Windows:

```bat
setx REMOVE_BG_API_KEY "SUA_CHAVE_AQUI"
```

Feche e abra o terminal/app de novo. Depois use o modo `auto` ou `api`.

Tambem da para passar a chave direto no comando:

```bat
python background_remover.py "foto.jpg" --mode api --api-key "SUA_CHAVE_AQUI" -o "foto-sem-fundo.png"
```

Observacao: a API pode consumir creditos da sua conta remove.bg.

### Opcao local

Para uma IA local, instale o removedor AI:

```bat
python -m pip install rembg
```

Depois use o modo `auto` ou `ai`. Se o Python instalado nao aceitar `rembg`, o app continua funcionando nos modos `api`, `border` e `checker`.
