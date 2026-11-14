# Empacotamento do Warsaw

Empacotamento RPM do módulo de segurança oficial Warsaw x86_64, da Topaz OFD
(antiga GAS Tecnologia / Diebold Nixdorf), exigido por vários bancos
brasileiros para o internet banking. O pacote é republicado nos repositórios
assinados do OBS do Lyra OS.

Este repositório só contém metadados de empacotamento; o Warsaw não é código
do Lyra. O conteúdo é redistribuído byte a byte.

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
- o RPM é assinado pela chave do projeto OBS do Lyra, e o release é
  `3.lyra1`, para substituir o `2.21.4-3` do fabricante, que não é assinado,
  caso ele já esteja instalado;
- o `%post` não ativa nem inicia o `warsaw.service`. O cartão "Bancos" do
  Vega ativa e desativa o serviço só quando o usuário pede, e o `%preun` para
  e desativa o serviço na remoção;
- na remoção, o `%preun` também mata os processos auxiliares que sobrarem
  (`core`, `sysdss`, `wsatspi` e `wsupdsl`) e o `%postun` apaga os diretórios
  privados do Warsaw em `/usr/local`, como faz o `postuninstall` oficial, para
  que nada sobreviva ao pacote;
- o `90-warsaw.preset` desativa a unit para o `systemctl preset` e para o
  primeiro boot.

O RPM oficial não tem assinatura. A cadeia de confiança é o SHA-256 fixado no
`_service` mais a assinatura do projeto OBS.

A Topaz publica o mesmo conteúdo para o Banco do Brasil
(`bb/downloads/ws/warsaw_setup64.rpm`) e para a Caixa
(`cef/warsaw/install/GBPCEFwr64.rpm`). Os dois espelhos são idênticos byte a
byte e têm o mesmo SHA-256 fixado. A verificação diária de `upstream-versions`
do `lyra-ecosystem` baixa os dois e avisa quando qualquer um mudar, incluindo o
`Last-Modified`. Essa verificação entra com o PR
[lyra-ecosystem#86](https://github.com/lyra-os-linux/lyra-ecosystem/pull/86).

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
