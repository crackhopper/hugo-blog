---
id: art_7aff55431892c03c2cbfaba121d4206d
title: Jupyter开发
tags:
draft: true
---

https://github.com/jupyterlab/jupyterlab/blob/3.3.x/docs/source/developer/contributing.rst


jlpm: The jlpm command is a JupyterLab-provided, locked version of the yarn package manager. If you have yarn installed already, you can use the yarn command when developing, and it will use the local version of yarn in jupyterlab/yarn.js when run in the repository or a built application directory.

https://github.com/jupyterlab/jupyterlab/issues/3281

??
To install JupyterLab in isolation for a single conda/virtual environment, you can add the --sys-prefix flag to the extension activation above; this will tie the installation to the sys.prefix location of your environment, without writing anything in your user-wide settings area (which are visible to all your envs):
??

jupyter lab --dev-mode

If you want to change the TypeScript code and rebuild on the fly (needs page refresh after each rebuild):

jupyter lab --dev-mode --watch


jest: need more docs


throttling


Galata 

