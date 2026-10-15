# Lâmina de Carvalho — RPG 3D em Python

RPG 3D em terceira pessoa feito com [Ursina](https://www.ursinaengine.org/) (sobre o Panda3D).
O herói começa na Vila de Carvalho só com uma **espada de madeira** e 30 moedas. Ele derrota
monstros, compra comida, ferramentas e poções, coleta madeira e pedra e fabrica armas melhores.

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

## Testes

Rode de dentro da pasta `rpg3d`:

```bash
python tests/test_jogo.py
```
Teste automático, sem abrir janela: carrega o mundo, simula combate, visita as regiões,
compra em todas as lojas, testa fome, coleta com cada ferramenta, fabrica armas, abre o
inventário, morre, renasce e pausa. Mostra `OK`/`FALHA` para cada verificação.

```bash
python tests/test_janela.py
```
Teste visual: abre o jogo por ~15 s, joga sozinho (lojas, corte de árvore, inventário,
combate) e fecha, mostrando o FPS médio. Não mexa no mouse enquanto roda.

Os dois salvam screenshots em `tests/screenshots/` (só o teste em janela mostra a interface).

```bash
python tests/test_cena.py
```
Toca a cena de abertura (2× mais rápida), tira screenshots ao longo dela e confere o estado final;
depois testa pular a cena com Esc.

```bash
python tests/benchmark.py
```
Mede o tempo de frame em três pontos do mapa, separando o custo do Python (lógica) e o da
renderização (GPU).

## Desempenho

- **Névoa + distância de visão**: o que está a mais de 64 m não é desenhado; a névoa (que começa
  em 26 m) esconde esse limite e se funde ao céu. Ajuste em `settings.py` (`FOG_START`, `FOG_END`,
  `VIEW_DISTANCE`).
- **Mapa em pedaços**: o cenário é dividido em blocos de 24 m; a GPU descarta os blocos fora da
  visão e fora da área de sombra.
- **Mobs e moedas dormentes**: a mais de 70 m do jogador eles ficam congelados (não são desenhados
  nem atualizados) e acordam abaixo de 62 m com a mesma posição, vida e estado.
- **Sombras mais leves**: mapa de sombra 2048 e 2×2 amostras por pixel (`SHADOW_MAP_SIZE`,
  `SHADOW_SAMPLES`).
- **Dica para notebooks com duas placas de vídeo**: no Windows, em *Configurações → Sistema →
  Tela → Elementos gráficos*, adicione o `python.exe` e escolha **Alto desempenho** para o jogo
  usar a placa dedicada (ex.: NVIDIA) em vez da integrada.

## Controles

| Tecla | Ação |
|---|---|
| W A S D | mover (relativo à câmera) |
| Mouse | girar a câmera |
| Clique esquerdo | atacar / usar a ferramenta equipada |
| 1 – 6 | trocar a arma/ferramenta (barra embaixo da tela) |
| F | falar com o vendedor (perto de uma loja) |
| Tab | inventário |
| C | comer (escolhe a fruta que melhor enche a fome) |
| E | beber poção |
| Shift | correr (gasta mais fome) |
| Espaço | pular |
| Scroll | zoom da câmera |
| M | liga/desliga a música |
| Esc | fechar menu / pausar (Q no menu de pausa sai do jogo) |
| R | renascer depois de morrer |

## História — Capítulo 1: A Noite dos Goblins

Ao começar um **Novo jogo**, toca a cena de abertura (~1 min com as falas; **Esc** pula, **Espaço**
avança as falas):

1. Meia-noite na Vila de Carvalho. Edmundo, pai de Arthur, volta para casa pela estrada leste.
2. Goblins saem da mata, cercam e levam Edmundo ("o chefe vai gostar desse aí").
3. O vizinho Joaquim vê tudo da porta de casa e corre até a casa de Arthur.
4. No quarto, Joaquim acorda Arthur e conta o que aconteceu.
5. Arthur sai desesperado para a vila. O jogo começa à noite e o dia nasce aos poucos (~90 s).

Objetivo inicial (aparece no HUD): resgatar o pai seguindo a estrada leste até o Acampamento Goblin.
O herói nasce (e renasce) na frente da casa dele, a de telhado azul a oeste da praça.

Para criar novas cenas, veja `cutscene.py` (o motor) e `story.py` (o roteiro da abertura): o roteiro
é uma sequência de passos como `yield cs.say('Joaquim', 'Arthur, acorda!')` ou
`yield cs.camera(posição, look=ator, duration=1.5)`.

## Salvar e carregar

- Ao abrir o jogo aparece a **tela inicial**: *Continuar* (mostra nível, moedas, tempo de jogo e
  data do save) ou *Novo jogo* (pede confirmação se já existir um save). Enter escolhe a opção principal.
- O jogo **salva sozinho a cada 60 s** de jogo, ao **fechar a janela** e com **Q** na pausa.
  Para salvar na hora, pause (Esc) e aperte **G**.
- É salvo: nível, XP, vida, fome, moedas, abates, posição, inventário, item equipado, árvores/rochas/
  plantas já coletadas e as moedas no chão (no mesmo lugar). Os monstros renascem ao carregar.
- O save fica em `saves/save.json`, com a versão anterior em `save.json.bak`. Se o save corromper,
  o jogo usa o backup automaticamente. Para começar do zero, apague a pasta `saves/`.
- Os testes usam uma pasta temporária e **nunca** mexem no seu save.

## Música

Trilha ambiente **composta e sintetizada no próprio código** (music.py, sem arquivos baixados):
120 BPM em Dó maior, 48 s em loop contínuo, com tema (A), ponte mais animada (B) e resolução (C).
Bateria, baixo, acordes, arpejo e melodia com eco. Na primeira execução ela é gerada em
ssets/ (cerca de 2 s); depois só é carregada. Abaixa na pausa e ao morrer; **M** liga/desliga.
Volume em settings.py (MUSIC_VOLUME). Para mudar a música, edite as listas de music.py,
aumente VERSION e rode o jogo (ou python music.py para só gerar o arquivo).

## Lojas (praça da vila)

| Loja | Vende |
|---|---|
| **Quitanda da Dona Flora** | Maçã (5), Banana (6), Uvas (8), Pêra (10): cada uma cura vida e enche a fome |
| **Ferraria do Bruno** | Picareta (40), Machado (35), Foice (25) e **fabrica armas de pedra** |
| **Cabana da Bruxa Morgana** | Poção de Vida (25, cura 40%) e Poção de Vida Grande (60, cura 100%) |

Poções **não** caem de monstros: só a bruxa vende.

## Fome

- A barra de fome cai com o tempo (cheia dura ~8 minutos; correr gasta 2,5× mais).
- Acima de 60: a vida regenera devagar em qualquer lugar.
- Abaixo de 25: aviso para comer.
- Em 0: você perde vida a cada segundo, não consegue correr e a vila não te cura.

## Coleta e fabricação

| Recurso | Ferramenta | Dá |
|---|---|---|
| Árvore | Machado | Madeira (4 golpes, 6 no total) |
| Rocha | Picareta | Pedra (5 golpes, 7 no total) |
| Planta | Foice | Ervas (e às vezes uma maçã ou uvas) |

Os recursos voltam a crescer depois de alguns minutos.

| Arma | Dano | Receita (na Ferraria) |
|---|---|---|
| Espada de Madeira | 5 | inicial |
| Espada de Pedra | 9 | 4 Madeira + 8 Pedra |
| Martelo de Pedra | 15 (lento) | 6 Madeira + 14 Pedra |

## O mundo

| Região | Inimigo | Perigo |
|---|---|---|
| Vila de Carvalho (centro) | — zona segura, regenera vida | — |
| Campina dos Slimes (sudoeste) e Bosque do Sul | Slime | baixo |
| Acampamento Goblin (leste) | Goblin | médio |
| Cemitério Esquecido (norte) | Esqueleto | alto |

Os inimigos **avisam antes de atacar** (o slime se achata, o goblin e o esqueleto erguem a arma),
então dá para recuar e desviar. O esqueleto não é interrompido pelos seus golpes.

## Sistemas de RPG

- **XP e níveis**: cada nível dá +15 de vida máxima, +1 de dano e cura total.
- **Moedas**: caem dos inimigos e são atraídas quando você chega perto.
- **Crítico**: 12% de chance de causar 1,8× de dano (número amarelo).
- **Morte**: você renasce na vila e perde 25% das moedas.

## Estrutura do código

| Arquivo | Conteúdo |
|---|---|
| `main.py` | ponto de entrada |
| `game.py` | loop principal, spawner, regiões, lojas, menus, pausa e game over |
| `player.py` | herói: movimento, câmera, combate, ferramentas, inventário, fome |
| `catalog.py` | **todos os itens** (comida, poções, ferramentas, armas, materiais) e receitas |
| `inventory.py` | inventário (quantidades por item) |
| `shops.py` | dados das lojas e os vendedores |
| `menus.py` | telas de loja e de inventário |
| `resources.py` | árvores, rochas e plantas coletáveis |
| `enemies.py` | IA compartilhada + Slime, Goblin e Esqueleto |
| `weapons.py` | modelos 3D das armas e ferramentas na mão |
| `items.py` | moedas que caem dos inimigos |
| `world.py` | construção do mapa, barracas das lojas e colisão |
| `models.py` | formas low-poly geradas em código e otimizações de desenho |
| `ui.py` | HUD, barra de itens, números de dano, telas de pausa/morte |
| `sounds.py` | efeitos sonoros retrô gerados na hora |
| `music.py` | composição e síntese da música ambiente |
| `save.py` | salvar/carregar o progresso (JSON com backup) |
| `cutscene.py` | motor de cenas: câmera, falas, fades, atores |
| `story.py` | a história: cena de abertura e objetivo do capítulo 1 |
| `settings.py` | constantes de balanceamento (incluindo a fome) e cores |

Para criar um item novo, adicione-o em `catalog.py`; para vendê-lo, coloque o id na lista
`stock` da loja em `shops.py`. Novas receitas vão em `RECIPES` (`catalog.py`).
