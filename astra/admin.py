from django.contrib import admin
from django.db.models import Q, Sum

from astra.models import (
    Approvisionnement,
    Categorie,
    Client,
    Fournisseur,
    Produit,
    Token,
    TokenVerification,
    Vente,
    NotificationPlateforme,
    Utilisateur,
)


# ============================================================
# CATEGORIES
# ============================================================

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "nom",
    )

    search_fields = (
        "nom",
    )

    ordering = (
        "nom",
    )


# ============================================================
# VENTES
# ============================================================

@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "reference",
        "client",
        "date_vente",
        "montant_total",
        "mode_paiement",
        "statut",
        "est_archive",
    )

    search_fields = (
        "reference",
        "client__nom",
        "client__prenom",
    )

    list_filter = (
        "statut",
        "mode_paiement",
        "est_archive",
        "date_vente",
    )

    ordering = (
        "-date_vente",
    )


# ============================================================
# FOURNISSEURS
# ============================================================

@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "nom",
        "contact",
        "telephone",
        "email",
        "is_active",
    )

    search_fields = (
        "nom",
        "contact",
        "telephone",
        "email",
    )

    list_filter = (
        "is_active",
    )


# ============================================================
# APPROVISIONNEMENTS
# ============================================================

@admin.register(Approvisionnement)
class ApprovisionnementAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "reference",
        "fournisseur",
        "date_creation",
        "montant_total",
        "statut",
        "is_active",
    )

    search_fields = (
        "reference",
        "fournisseur__nom",
    )

    list_filter = (
        "statut",
        "is_active",
        "date_creation",
    )

    ordering = (
        "-date_creation",
    )


# ============================================================
# TOKEN VERIFICATION
# ============================================================

@admin.register(TokenVerification)
class TokenVerificationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "email",
        "token",
        "role",
        "date_creation",
        "utilise",
    )

    search_fields = (
        "email",
        "token",
    )

    list_filter = (
        "role",
        "utilise",
        "date_creation",
    )


# ============================================================
# TOKEN
# ============================================================

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "email",
        "valeur_token",
        "role",
        "date_creation",
        "date_expiration",
    )

    search_fields = (
        "email",
        "valeur_token",
    )

    list_filter = (
        "role",
        "date_creation",
    )


# ============================================================
# NOTIFICATIONS PLATEFORME
# ============================================================

@admin.register(NotificationPlateforme)
class NotificationPlateformeAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "titre",
        "categorie",
        "lu",
        "date_creation",
    )

    search_fields = (
        "titre",
        "message",
    )

    list_filter = (
        "categorie",
        "lu",
        "date_creation",
    )

    ordering = (
        "-date_creation",
    )


# ============================================================
# PRODUITS
# ============================================================

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):

    list_display = (
        "reference",
        "nom",
        "categorie",
        "prix_vente",
        "stock",
        "stock_status",
        "is_active",
    )

    search_fields = (
        "nom",
        "reference",
    )

    list_filter = (
        "categorie",
        "is_active",
    )

    fieldsets = (
        (
            "Informations Générales",
            {
                "fields": (
                    "nom",
                    "categorie",
                    "reference",
                    "image",
                    "is_active",
                )
            }
        ),
        (
            "Prix et Stock",
            {
                "fields": (
                    "prix_achat",
                    "prix_vente",
                    "stock",
                    "seuil_alerte",
                )
            }
        ),
        (
            "Propriétés spécifiques (Ordinateurs & Composants)",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "processeur",
                    "ram",
                    "stockage_disque",
                    "taille_ecran",
                ),
            }
        ),
    )

    def stock_status(self, obj):
        if obj.stock <= obj.seuil_alerte:
            return "⚠ Stock faible"

        return "✓ Stock normal"

    stock_status.short_description = "État du stock"


# ============================================================
# CLIENTS
# ============================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "reference",
        "nom",
        "prenom",
        "telephone",
        "email",
        "total_calcule",
        "is_active",
        "date_inscription",
    )

    search_fields = (
        "nom",
        "prenom",
        "telephone",
        "email",
        "reference",
    )

    list_filter = (
        "is_active",
        "date_inscription",
    )

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        queryset = queryset.annotate(
            total_sum=Sum(
                "ventes__montant_total",
                filter=Q(
                    ventes__est_archive=False
                )
            )
        )

        return queryset

    def total_calcule(self, obj):

        return obj.total_sum or 0

    total_calcule.short_description = "Total Dépense"
    total_calcule.admin_order_field = "total_sum"


# ============================================================
# UTILISATEURS ASTRA TECH
# ============================================================
#
# IMPORTANT :
# C'est ici que tu retrouveras TOUS les nouveaux comptes
# créés depuis le formulaire d'inscription.
# ============================================================

@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "nom",
        "prenom",
        "email",
        "telephone",
        "role",
        "is_active",
        "date_inscription",
    )

    search_fields = (
        "nom",
        "prenom",
        "email",
        "telephone",
    )

    list_filter = (
        "role",
        "is_active",
        "date_inscription",
    )

    ordering = (
        "-date_inscription",
    )

    readonly_fields = (
        "date_inscription",
    )

    fieldsets = (
        (
            "Informations personnelles",
            {
                "fields": (
                    "nom",
                    "prenom",
                    "email",
                    "telephone",
                )
            }
        ),
        (
            "Accès ASTRA TECH",
            {
                "fields": (
                    "role",
                    "password",
                    "is_active",
                )
            }
        ),
        (
            "Informations système",
            {
                "fields": (
                    "date_inscription",
                )
            }
        ),
    )


# ============================================================
# MOUVEMENTS DE STOCK
# ============================================================

from astra.models import MouvementStock


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "produit",
        "type_mouvement",
        "quantite",
        "date",
    )

    search_fields = (
        "produit__nom",
        "produit__reference",
    )

    list_filter = (
        "type_mouvement",
        "date",
    )

    ordering = (
        "-date",
    )


# ============================================================
# PARAMETRES GLOBAUX
# ============================================================

from astra.models import ParametreGlobal


@admin.register(ParametreGlobal)
class ParametreGlobalAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "nom_boutique",
        "verrou_commercial",
        "verrou_admin",
        "seuil_stock",
        "taux_tva",
    )


# ============================================================
# UTILISATEUR ACCES
# ============================================================

from astra.models import UtilisateurAcces


@admin.register(UtilisateurAcces)
class UtilisateurAccesAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "nom",
        "prenom",
        "email",
        "telephone",
        "role",
        "est_actif",
        "date_inscription",
        "token_expiration",
    )

    search_fields = (
        "nom",
        "prenom",
        "email",
        "telephone",
    )

    list_filter = (
        "role",
        "est_actif",
        "date_inscription",
    )

    readonly_fields = (
        "date_inscription",
        "token_expiration",
    )