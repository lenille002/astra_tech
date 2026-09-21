## Premier administrateur sur Vercel

Dans les variables d'environnement du projet Vercel, ajouter temporairement :

```text
ASTRA_ADMIN_NOM=VotreNom
ASTRA_ADMIN_PRENOM=VotrePrenom
ASTRA_ADMIN_EMAIL=admin@example.com
ASTRA_ADMIN_PASSWORD=MotDePasseFort
```

Déployer ensuite, ouvrir une fois la page `/` ou `/connexion/`, puis se connecter avec ces informations. Le compte sera créé dans la table `Utilisateur` avec le rôle `admin` et pourra ouvrir `/utilisateurs/`.

Après la première connexion réussie, supprimer `ASTRA_ADMIN_PASSWORD` et les autres variables `ASTRA_ADMIN_*` de Vercel, puis redéployer. Le compte déjà créé restera dans la base de données.
