from django.urls import path
from . import views

app_name = "astra"

urlpatterns = [

    # =========================================================
    # AUTHENTIFICATION & PAGES PRINCIPALES
    # =========================================================

     path("", views.login_view, name="login"),
    path("connexion/", views.login_view, name="connexion"),

   path("accueil/", views.accueil, name="accueil"),
    path("logout/", views.deconnexion, name="logout"),


   path("tokens/", views.token_accueil, name="token_accueil"),

    

path(
    "fournisseurs/",
    views.fournisseurs,
    name="fournisseurs"
),

path(
    "fournisseurs/supprimer/<int:pk>/",
    views.supprimer_fournisseur,
    name="supprimer_fournisseur"
),

path(
    "fournisseurs/email/<int:fournisseur_id>/",
    views.envoyer_email_fournisseur,
    name="envoyer_email_fournisseur"
),

# ==============================
# ESPACE FOURNISSEUR
# ==============================

    path(
        "fournisseur/",
        views.espace_fournisseur,
        name="fournisseur_dashboard"
    ),

  path(
        "fournisseur/<int:pk>/",
        views.espace_fournisseur,
        name="espace_fournisseur"
    ),

# ==============================
# CONNEXION FOURNISSEUR
# ==============================

path(
    "fournisseur/<int:fournisseur_id>/connexion/",
    views.connexion_fournisseur,
    name="connexion_fournisseur"
),

path(
    "fournisseur/<int:fournisseur_id>/verification-app/",
    views.verification_mot_de_passe_app,
    name="verifier_mot_de_passe_app"
),

path(
    "fournisseur/<int:pk>/deconnexion/",
    views.deconnexion_fournisseur,
    name="deconnexion_fournisseur"
),
    # =========================================================
    # VENTES
    # =========================================================

    path("ventes/", views.ventes_view, name="ventes"),
    path(
        "vente/details/<int:vente_id>/",
        views.details_vente,
        name="details_vente"
    ),

    path(
        "vente/enregistrer/",
        views.enregistrer_vente,
        name="enregistrer_vente"
    ),

    path(
        "vente/supprimer/<int:vente_id>/",
        views.supprimer_vente,
        name="supprimer_vente"
    ),

    path(
        "vente/modifier/<int:vente_id>/",
        views.modifier_vente,
        name="modifier_vente"
    ),


    # =========================================================
    # STOCK
    # =========================================================

    # Dans astra/urls.py
    
    path("stocks/", views.stock_view, name="stocks"),

    path(
        "stock/ajouter/",
        views.ajouter_produit,
        name="ajouter_produit"
    ),

    path(
        "stock/modifier/<int:product_id>/",
        views.modifier_produit,
        name="modifier_produit"
    ),

    path(
        "stock/supprimer/<int:product_id>/",
        views.supprimer_produit,
        name="supprimer_produit"
    ),


    # =========================================================
    # APPROVISIONNEMENTS
    # =========================================================
    
     path(
        "approvisionnement/",
        views.approvisionnements_view,
        name="approvisionnement"
    ),

    path(
        "approvisionnements/ajouter/",
        views.ajouter_approvisionnement,
        name="ajouter_approvisionnement"
    ),

    path(
        "approvisionnements/<int:pk>/details/",
        views.details_approvisionnement,
        name="detail_approvisionnement"
    ),

    path(
        "approvisionnements/<int:pk>/modifier/",
        views.modifier_approvisionnement,
        name="modifier_approvisionnement"
    ),

    path(
        "approvisionnements/<int:pk>/supprimer/",
        views.supprimer_approvisionnement,
        name="supprimer_approvisionnement"
    ),


    # =========================================================
    # RAPPORTS
    # =========================================================

    path(
        "rapports/",
        views.rapports,
        name="rapports"
    ),

    path(
        "rapports/reset-page/",
        views.reset_page_rapports,
        name="reset_page_rapports"
    ),

    path(
        "propos/",
        views.propos,
        name="propos"
    ),


    # =========================================================
    # CLIENTS
    # =========================================================
    
    path(
        "clients/",
        views.gestion_clients,
        name="clients"
    ),

    path(
        "client/inscription/",
        views.client_register,
        name="client_register"
    ),

    # Conserve l'alias 'register' pointant sur la même vue pour éviter les erreurs dans les templates existants
    path(
        "client/register/",
        views.client_register,
        name="register"
    ),

    path(
        "client/<int:client_id>/connexion/",
        views.client_login,
        name="client_login"
    ),

    path(
        "client/<int:client_id>/cahier/",
        views.detail_client_activites,
        name="detail_client_activites"
    ),

    path(
        "client/<int:client_id>/supprimer/",
        views.supprimer_client,
        name="supprimer_client"
    ),

    path(
        "client/<int:client_id>/modifier/",
        views.modifier_client,
        name="modifier_client"
    ),
    
    path(
        "client/<int:client_id>/espace/",
        views.espace_client,
        name="espace_client"
    ),

    path(
        "client/mot-de-passe-oublie/",
        views.mot_de_passe_oublie_client,
        name="mot_de_passe_oublie_client"
    ),

    path(
        "client/<int:client_id>/modifier-mdp/",
        views.modifier_mot_de_passe_client,
        name="modifier_mot_de_passe_client"
    ),


    # =========================================================
    # API & TOKENS
    # =========================================================

    path(
        "api/generer-token/",
        views.generer_token_api,
        name="generer_token_api"
    ),

    path(
        "login-token/",
        views.LoginWithTokenView.as_view(),
        name="login_token"
    ),


    # =========================================================
    # UTILISATEURS
    # =========================================================

    path(
        "utilisateurs/",
        views.users_page_view,
        name="page_utilisateurs"
    ),

    path(
        "api/utilisateurs/",
        views.api_users_list_create,
        name="api_users_list_create"
    ),

    path(
        "api/utilisateurs/<int:pk>/",
        views.api_user_detail_update_delete,
        name="api_user_detail_update_delete"
    ),


    # =========================================================
    # PERMISSIONS
    # =========================================================

    path(
        "permissions/",
        views.permissions_page_view,
        name="permissions_page"
    ),

    path(
        "api/permissions/",
        views.api_save_permissions,
        name="api_save_permissions"
    ),


    # =========================================================
    # HISTORIQUES
    # =========================================================

    path(
        "historiques/",
        views.historiques_page_view,
        name="historiques_page"
    ),


    # =========================================================
    # PARAMÈTRES
    # =========================================================

    path(
        "parametres/",
        views.parametres_page_view,
        name="parametres_page"
    ),

    path(
        "api/parametres/",
        views.api_save_parametres,
        name="api_save_parametres"
    ),


    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    path(
        "notifications/marquer-lues/",
        views.marquer_toutes_comme_lues,
        name="marquer_lues"
    ),

    path(
        "notifications/<int:pk>/",
        views.detail_notification,
        name="detail_notification"
    ),
]