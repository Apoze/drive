# Domain Docs

Avant d’explorer un domaine, lire `CONTEXT.md` à la racine et les ADR
pertinentes sous `docs/adr/`, lorsqu’ils existent.

Le dépôt utilise un contexte unique :

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

Utiliser dans les specs, tickets et tests le vocabulaire défini dans
`CONTEXT.md`. Si une proposition contredit une ADR existante, signaler
explicitement le conflit.

L’absence de ces fichiers n’est pas une erreur : ils sont créés seulement
lorsqu’une décision de domaine réelle doit être enregistrée.
