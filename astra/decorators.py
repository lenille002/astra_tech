from functools import wraps
from django.shortcuts import redirect


# =========================================================
# NORMALISATION DES RÔLES
# =========================================================
# Tous les noms possibles d'un rôle sont transformés vers
# un seul rôle canonique.
# =========================================================

ROLE_ALIASES = {
    # ADMIN
    "admin": "admin",
    "administrateur": "admin",
    "administrateurs": "admin",

    # VENTE
    "vente": "vente",
    "vendeur": "vente",
    "vendeurs": "vente",
    "caissier": "vente",

    # CLIENT
    "client": "client",
    "clients": "client",

    # FOURNISSEUR
    "fournisseur": "fournisseur",
    "fournisseurs": "fournisseur",

    # APPROVISIONNEMENT
    "approvisionnement": "approvisionnement",
    "approvisionnements": "approvisionnement",
    "approvisionneur": "approvisionnement",

    # STOCK
    "stock": "stocks",
    "stocks": "stocks",

    # RAPPORT
    "rapport": "rapports",
    "rapports": "rapports",
}


# =========================================================
# PERMISSIONS DES RÔLES
# =========================================================
# Les noms correspondent aux pages principales de ASTRA TECH.
# =========================================================

ROLE_PERMISSIONS = {
    "admin": {
        "ventes",
        "stocks",
        "approvisionnements",
        "clients",
        "fournisseurs",
        "rapports",
        "propos",
    },

    "vente": {
        "ventes",
        "clients",
        "propos",
    },

    "client": {
        "ventes",
        "clients",
        "propos",
    },

    "fournisseur": {
        "fournisseurs",
        "approvisionnements",
        "propos",
    },

    "approvisionnement": {
        "fournisseurs",
        "approvisionnements",
        "propos",
    },

    "stocks": {
        "stocks",
        "propos",
    },

    "rapports": {
        "rapports",
        "propos",
    },
}


# =========================================================
# NORMALISER UN RÔLE
# =========================================================

def normaliser_role(role):
    """
    Transforme n'importe quel alias connu en rôle canonique.

    Exemples :
        administrateur -> admin
        vendeur -> vente
        clients -> client
        stock -> stocks
        rapport -> rapports
    """

    if not role:
        return ""

    role = str(role).strip().lower()

    return ROLE_ALIASES.get(role, role)


# =========================================================
# RÉCUPÉRER LE RÔLE DE L'UTILISATEUR CONNECTÉ
# =========================================================

def get_user_role(request):
    """
    Récupère le rôle depuis la session ASTRA TECH.

    Le login_view() enregistre actuellement :
        request.session["user_role"]
    """

    role = request.session.get("user_role", "")

    return normaliser_role(role)


# =========================================================
# VÉRIFIER SI L'UTILISATEUR EST CONNECTÉ
# =========================================================

def utilisateur_connecte(request):
    """
    Vérifie si un utilisateur ASTRA TECH est connecté.

    Le système utilise la session personnalisée et non
    uniquement request.user.
    """

    return (
        request.session.get("connecte") is True
        and request.session.get("utilisateur_id") is not None
    )


# =========================================================
# VÉRIFIER UNE PERMISSION
# =========================================================

def utilisateur_a_permission(request, permission):
    """
    Vérifie si le rôle actuel possède une permission donnée.

    Exemple :
        utilisateur_a_permission(request, "stocks")
    """

    role = get_user_role(request)

    if not role:
        return False

    permissions = ROLE_PERMISSIONS.get(role, set())

    return permission in permissions


# =========================================================
# DÉCORATEUR STRICT ASTRA TECH
# =========================================================

def verifier_acces_strict(allowed_roles=None):
    """
    Décorateur principal utilisé par les vues ASTRA TECH.

    Exemple :

        @verifier_acces_strict(
            allowed_roles=["admin", "stocks"]
        )
        def stock_view(request):
            ...

    Les rôles sont automatiquement normalisés.

    IMPORTANT :
    Si allowed_roles est None ou vide, la vue est accessible
    à tout utilisateur ASTRA TECH connecté.

    Cela permet de conserver la compatibilité avec les vues
    existantes utilisant simplement :

        @verifier_acces_strict
    """

    # -----------------------------------------------------
    # Support de :
    #
    # @verifier_acces_strict
    #
    # et :
    #
    # @verifier_acces_strict(...)
    # -----------------------------------------------------

    if callable(allowed_roles):
        view_func = allowed_roles

        @wraps(view_func)
        def _wrapped_without_roles(request, *args, **kwargs):

            if not utilisateur_connecte(request):
                return redirect("astra:login")

            return view_func(request, *args, **kwargs)

        return _wrapped_without_roles

    # -----------------------------------------------------
    # Si aucun rôle n'est fourni
    # -----------------------------------------------------

    if allowed_roles is None:
        allowed_roles = []

    # -----------------------------------------------------
    # Normalisation des rôles autorisés
    # -----------------------------------------------------

    allowed_roles_normalises = {
        normaliser_role(role)
        for role in allowed_roles
        if role
    }

    # -----------------------------------------------------
    # Décorateur
    # -----------------------------------------------------

    def decorator(view_func):

        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            # =================================================
            # 1. UTILISATEUR NON CONNECTÉ
            # =================================================

            if not utilisateur_connecte(request):
                return redirect("astra:login")

            # =================================================
            # 2. RÉCUPÉRER LE RÔLE
            # =================================================

            user_role = get_user_role(request)

            # =================================================
            # 3. RÔLE INVALIDE
            # =================================================

            if not user_role:
                request.session.flush()
                return redirect("astra:login")

            # =================================================
            # 4. ADMINISTRATEUR
            # =================================================
            # L'administrateur possède tous les droits.
            # =================================================

            if user_role == "admin":
                return view_func(request, *args, **kwargs)

            # =================================================
            # 5. AUCUN RÔLE SPÉCIFIQUE
            # =================================================
            # Compatibilité avec les anciennes vues utilisant :
            #
            # @verifier_acces_strict
            #
            # ou :
            #
            # @verifier_acces_strict()
            # =================================================

            if not allowed_roles_normalises:
                return view_func(request, *args, **kwargs)

            # =================================================
            # 6. VÉRIFICATION DU RÔLE
            # =================================================

            if user_role in allowed_roles_normalises:
                return view_func(request, *args, **kwargs)

            # =================================================
            # 7. ACCÈS REFUSÉ
            # =================================================
            # On renvoie l'utilisateur vers sa page principale.
            # =================================================

            role_redirects = {
                "vente": "astra:ventes",
                "client": "astra:ventes",
                "fournisseur": "astra:fournisseur_dashboard",
                "approvisionnement": "astra:approvisionnement",
                "stocks": "astra:stocks",
                "rapports": "astra:rapports",
            }

            redirect_name = role_redirects.get(
                user_role,
                "astra:login"
            )

            return redirect(redirect_name)

        return _wrapped_view

    return decorator


# =========================================================
# DÉCORATEUR ROLE_REQUIRED
# =========================================================

def role_required(allowed_roles=None):
    """
    Alias compatible avec les anciennes vues.

    Exemple :

        @role_required(["admin"])
        def ma_vue(request):
            ...
    """

    return verifier_acces_strict(allowed_roles)


# =========================================================
# ALIAS VERIFIER_ROLE
# =========================================================

def verifier_role(allowed_roles=None):
    """
    Alias de compatibilité.
    """

    return verifier_acces_strict(allowed_roles)


# =========================================================
# OBTENIR LES PERMISSIONS DU RÔLE
# =========================================================

def get_user_permissions(request):
    """
    Retourne l'ensemble des pages accessibles
    par l'utilisateur connecté.
    """

    role = get_user_role(request)

    return ROLE_PERMISSIONS.get(role, set())