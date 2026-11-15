<p align="center">
  <img src="docs/topaz-logo.svg" alt="Logo da Topaz, fabricante do Warsaw" width="280">
</p>

# Empacotamento do Warsaw

Empacotamento RPM do módulo de segurança oficial Warsaw x86_64, da Topaz OFD
(antiga GAS Tecnologia / Diebold Nixdorf), exigido por vários bancos
brasileiros para o internet banking. O pacote é republicado nos repositórios
assinados do OBS do Lyra OS.

Este repositório só contém metadados de empacotamento; o Warsaw não é código
do Lyra. O conteúdo é redistribuído byte a byte.

## Para que serve

O Warsaw é o "módulo de segurança" que alguns bancos brasileiros, como o Banco
do Brasil e a Caixa, exigem para liberar o internet banking no navegador. Sem
ele, o site do banco não deixa entrar na conta ou bloqueia operações como
pagamentos e transferências.

Ele roda em segundo plano como o serviço `warsaw.service` (o processo `core`).
O site do banco conversa com esse serviço local para identificar o computador
e proteger a sessão contra fraudes. Por isso o módulo precisa estar instalado e
em execução enquanto o usuário usa o banco.

No Lyra OS, o serviço não inicia sozinho: o cartão "Bancos" do Vega ativa o
Warsaw só quando o usuário pede e o desativa depois.

| Arquivo | Função |
| --- | --- |
| `_service` | Serviço de fonte do OBS: baixa o RPM oficial por HTTPS e confere o SHA-256 |
| `warsaw.spec` | Extrai o RPM oficial com `rpm2cpio` e instala os mesmos arquivos nos mesmos caminhos, sem compilar nem modificar nada |
| `warsaw-files.sha256` | SHA-256 fixado de cada arquivo empacotado, conferido no `%check` |
| `warsaw.preset` | Mantém o `warsaw.service` desativado, para que os presets do systemd não o ativem na instalação nem no primeiro boot |
| `warsaw.changes` | Changelog do RPM no formato do openSUSE |
| `warsaw-rpmlintrc` | Filtros do rpmlint para o layout do fabricante em `/usr/local` |

## O que muda em relação ao RPM oficial

Só os metadados mudam. Todos os binários, bibliotecas, configurações e dados
são idênticos, byte a byte, aos do `warsaw_setup64.rpm` 2.21.4-3:

- `Requires: procps` substitui o `procps-ng` original, que não existe no
  openSUSE (lá o pacote se chama `procps`);
- o RPM é assinado pela chave do projeto OBS do Lyra e tem `Epoch: 1`, para
  substituir o `2.21.4-3` do fabricante, que não é assinado, caso ele já
  esteja instalado. O OBS reescreve o release (`lp161.N.M`), e sem o epoch o
  `3` do fabricante seria considerado mais novo;
- o `%post` não ativa nem inicia o `warsaw.service`. O cartão "Bancos" do
  Vega ativa e desativa o serviço só quando o usuário pede, e o `%preun` para
  e desativa o serviço na remoção;
- ao substituir o RPM do fabricante, que habilita o serviço no boot, o
  `%post` desabilita o `warsaw.service` (sem pará-lo), para que ele volte a
  subir só quando o usuário pedir;
- na atualização, o `%pre` para o serviço e mata os processos auxiliares
  antes de trocar os arquivos, como faz o `%pre` oficial, e o `%posttrans`
  religa o serviço só se ele estava ativo;
- só o `gas.dbd` é marcado como `%config(noreplace)`, como no RPM oficial;
  os demais arquivos de `/usr/local/etc/warsaw` são dados do fabricante e
  acompanham cada atualização;
- na remoção, o `%preun` também mata os processos auxiliares que sobrarem
  (`core`, `sysdss`, `wsatspi` e `wsupdsl`) e o `%postun` apaga os diretórios
  privados do Warsaw em `/usr/local`, como faz o `postuninstall` oficial, para
  que nada sobreviva ao pacote;
- o `90-warsaw.preset` desativa a unit para o `systemctl preset` e para o
  primeiro boot.
- os scripts de instalação usam os macros de serviço do openSUSE
  (`%service_add_pre`, `%service_add_post`, `%service_del_preun` e
  `%service_del_postun`), no lugar das chamadas ao `systemctl` do fabricante.

O RPM oficial não tem assinatura. A cadeia de confiança é o SHA-256 fixado no
`_service` mais a assinatura do projeto OBS.

A Topaz publica o mesmo conteúdo para o Banco do Brasil
(`bb/downloads/ws/warsaw_setup64.rpm`) e para a Caixa
(`cef/warsaw/install/GBPCEFwr64.rpm`). Os dois espelhos são idênticos byte a
byte e têm o mesmo SHA-256 fixado. A verificação diária de `upstream-versions`
do `lyra-ecosystem` baixa os dois e avisa quando qualquer um mudar, incluindo o
`Last-Modified`. Essa verificação entra com o PR
[lyra-ecosystem#86](https://github.com/lyra-os-linux/lyra-ecosystem/pull/86).

## Riscos aceitos

O rpmlint do openSUSE aponta problemas que vêm dos arquivos do fabricante.
Corrigi-los exigiria modificar ou mover os binários, o que a licença não
permite. O mantenedor decidiu, em 15/11/2026, filtrá-los no
`warsaw-rpmlintrc` e documentá-los aqui:

- **pilha executável** (`executable-stack`) em
  `/usr/local/lib/warsaw/wsbrmu.so`: a biblioteca pede uma pilha executável,
  o que facilita a exploração de falhas de memória num processo que roda
  como root;
- **troca de usuário sem `setgroups`**
  (`missing-call-to-setgroups-before-setuid`) no `core`: ao trocar de
  usuário, o processo pode manter os grupos suplementares do root;
- **arquivos em `/usr/local`** (`filelist-forbidden-fhs23`): o openSUSE
  reserva `/usr/local` ao administrador. Além disso, `/usr/local` fica fora
  dos snapshots do Snapper, e um rollback deixa o RPM e os arquivos
  incoerentes ([#12](https://github.com/lyra-os-linux/warsaw/issues/12));
- **init script** (`deprecated-init-script` e
  `systemd-shadowed-initscript`): o `/etc/init.d/warsaw` faz parte do
  conteúdo oficial, mas o systemd usa o `warsaw.service` e ignora o script.

Por isso o `warsaw.service` fica desligado por padrão e só roda enquanto o
usuário usa o banco.

## Instalador e atualizador do fabricante

O conteúdo traz dois pontos de entrada que importam para as atualizações:

- `/usr/local/bin/warsaw/wsupdsl` **não** é um atualizador automático. É um
  vigia que reinicia o `warsaw.service` só quando o `core` morre.
- `/usr/bin/warsaw` é o instalador do fabricante. O `warsaw start` pode baixar
  componentes do fabricante por HTTP e gravar em `/usr/local`, fora do controle
  do RPM.

Não execute o instalador do fabricante. Gerencie o `warsaw.service`
empacotado, para que os arquivos instalados continuem pertencendo ao RPM e as
atualizações cheguem só pelo Zypper e pelos repositórios assinados do Lyra. Se
o fabricante passar a atualizar o `core` sozinho, esse comportamento precisa
ser documentado e controlado; hoje isso não acontece.

O pacote instala `/etc/init.d/warsaw` porque ele faz parte do conteúdo
oficial, mas o systemd usa `/usr/lib/systemd/system/warsaw.service`
(`Type=forking`, `ExecStart=/usr/local/bin/warsaw/core`,
`PIDFile=/var/run/core.pid`, `Restart=always`). O cartão do Vega deve usar o
`systemctl` diretamente, nunca o `warsaw start`.

Por causa do init script, `systemctl enable` e `systemctl disable` do
`warsaw.service` falham no Leap 16.1: o `systemctl` tenta sincronizar com o
`systemd-sysv-install`, que não existe. Assim, o serviço não pode ser
habilitado no boot, nem pelo `%post` do RPM do fabricante. É o comportamento
desejado: o Warsaw roda só enquanto o usuário usa o banco. O cartão "Bancos"
do Vega deve usar só `Services.SetServiceRunning` (`systemctl start` e
`stop`), nunca `Services.SetServiceEnabled`. O init script continua no
pacote por decisão do mantenedor (15/11/2026), porque faz parte do conteúdo
oficial. A evidência do teste está na
[#4](https://github.com/lyra-os-linux/warsaw/issues/4#issuecomment-6899362677).

## Licença

O RPM oficial declara `License: Redistributable, no modification permitted`,
enquanto o Warsaw Installer e os arquivos de licença empacotados são
LGPL-3.0-or-later. Este pacote redistribui os mesmos binários e bibliotecas,
sem modificá-los, e só ajusta os metadados do RPM. A interpretação adotada é
que isso é redistribuição, não modificação.

É preciso guardar uma confirmação por escrito da Topaz antes de promover o
pacote ao repositório de release. Se o fabricante não aceitar essa
interpretação, o pacote não pode ser redistribuído, e o cartão do Vega deve
usar o caminho de download guiado (vega#208/#263). Até lá, o pacote fica só no
staging. O acompanhamento está em
[lyra-ecosystem#66](https://github.com/lyra-os-linux/lyra-ecosystem/issues/66).

Os arquivos de licença do fabricante são instalados em
`/usr/share/licenses/warsaw/`.

## Build e validação

A CI roda a cada push na `main` e em cada pull request:

```sh
python3 -m unittest discover -s tests -v
rpmspec -P warsaw.spec >/dev/null
```

Os testes exigem:

- HTTPS e SHA-256 fixado para o RPM do fabricante;
- a dependência de `procps`;
- nenhuma ativação automática do serviço;
- o preset que desativa o serviço;
- um manifesto coerente com o conteúdo empacotado.

O build no OBS roda `sha256sum --check --strict` em cada arquivo empacotado
depois do `%install`; um arquivo com símbolos removidos ou modificado de
qualquer outra forma faz o build falhar. O `__os_install_post` fica desligado,
para que nenhum script `brp-*` mexa no conteúdo.

## Problemas conhecidos

- [#1](https://github.com/lyra-os-linux/warsaw/issues/1): uma atualização com
  o `warsaw.service` ativo mantém o `core` antigo rodando.
- [#2](https://github.com/lyra-os-linux/warsaw/issues/2): falta confirmar que o
  `pkill` da remoção encontra todos os processos auxiliares.
- [#3](https://github.com/lyra-os-linux/warsaw/issues/3): um arquivo novo do
  fabricante que fique fora do `warsaw-files.sha256` entra no pacote sem
  conferência de hash.
- [#4](https://github.com/lyra-os-linux/warsaw/issues/4): qualificação numa VM
  Leap 16.1 limpa, que ainda precisa provar que:
  - instalar, atualizar e remover não deixa arquivo órfão em `/usr/local`;
  - o `warsaw.service` só inicia quando ativado, funciona com SELinux em modo
    enforcing e, depois de parado, não deixa porta aberta nem processo
    inesperado;
  - o cartão "Bancos" do Vega ativa, verifica e desativa o serviço pelo
    contrato D-Bus existente (`Services.SetServiceEnabled` e
    `Services.SetServiceRunning`), sem chamar o instalador do fabricante.

## Atualização

Quando a Topaz publicar um RPM novo:

1. troque o SHA-256 no `_service` e baixe o arquivo de novo;
2. atualize o `warsaw-files.sha256` com o novo conteúdo;
3. suba `Version`/`Release`, acrescente uma entrada no `warsaw.changes` e
   atualize o `upstream-versions.toml` no `lyra-ecosystem` (as URLs dos dois
   espelhos);
4. construa no projeto de staging do OBS, qualifique no Leap 16.1 e só então
   promova.

## Créditos

O Warsaw é desenvolvido pela Topaz OFD (antiga GAS Tecnologia / Diebold
Nixdorf). Veja <https://www.topaz.com.br/ofd/>. Os arquivos de licença do
fabricante acompanham o RPM oficial.

O logo no topo deste README é marca da Topaz, copiado de
<https://www.topazevolution.com/>, e aparece só para identificar o fabricante.
O Warsaw não tem logo próprio publicado.
