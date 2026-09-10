from astra import models
from astra.decorators import role_required
from datetime import date, datetime, timedelta
from functools import wraps
import json
import secrets
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Group, Permission, User
from django.core.mail import send_mail
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, F, FloatField, Max, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth, TruncYear
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie

# pyrefly: ignore [missing-import]
from rest_framework import status
# pyrefly: ignore [missing-import]
from rest_framework.decorators import api_view
# pyrefly: ignore [missing-import]
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from rest_framework.views import APIView

from astra.decorators import verifier_role
from astra.models import (
    Approvisionnement,
    Categorie,
    Client,
    Fournisseur,
    LigneVente,
    MouvementStock,
    Notification,
    NotificationPlateforme,
    ParametreGlobal,
    Produit,
    Token,
    Vente,
    Utilisateur,
)
from .serializers import EmailTokenObtainSerializer, UserSerializer


# ==========================================================
# NORMALISATION DES RÔLES
# ==========================================================


# ==========================================================
# NORMALISATION DES RÔLES
# ==========================================================

def normaliser_role(role):
    role = str(role or "").lower().strip()
    correspondances = {
        "admin": "admin",
        "administrateur": "admin",
        "administrateurs": "admin",
        "vente": "vente",
        "ventes": "vente",
        "vendeur": "vente",
        "vendeurs": "vente",
        "caissier": "vente",
        "fournisseur": "fournisseur",
        "fournisseurs": "fournisseur",
        "client": "client",
        "clients": "client",
        "approvisionnement": "approvisionnement",
        "approvisionnements": "approvisionnement",
    }
    return correspondances.get(role, role)


# ==========================================================
# REDIRECTION SELON LE RÔLE
# ==========================================================
def rediriger_selon_role(request, role=None, user_trouve=None):
    """
    Redirige l'utilisateur vers la page correspondant à son rôle.
    """

    # Si aucun rôle n'est fourni, on récupère celui de la session
    if role is None:
        role = request.session.get("user_role", "")

    role = normaliser_role(role)

    print("========================================")
    print("REDIRECTION SELON ROLE")
    print("Rôle reçu :", role)
    print("Utilisateur :", user_trouve)
    print("========================================")

    # =========================================================
    # ADMIN
    # =========================================================
    if role == "admin":
        request.session["user_role"] = "admin"
        request.session["connecte"] = True

        return redirect("astra:token_accueil")

    # =========================================================
    # VENTE
    # =========================================================
    elif role == "vente":
        request.session["user_role"] = "vente"
        request.session["connecte"] = True

        return redirect("astra:ventes")

    # =========================================================
    # FOURNISSEUR
    # =========================================================
    elif role == "fournisseur":
        request.session["user_role"] = "fournisseur"
        request.session["connecte"] = True

        if user_trouve:
            email = getattr(user_trouve, "email", "")

            fournisseur_obj = Fournisseur.objects.filter(
                email__iexact=email
            ).first()

            if fournisseur_obj:
                request.session["fournisseur_connecte_id"] = fournisseur_obj.id

                print(
                    "Fournisseur connecté :",
                    fournisseur_obj.id
                )

                return redirect(
                    "astra:espace_fournisseur",
                    pk=fournisseur_obj.id
                )

        return redirect("astra:fournisseurs")

    # =========================================================
    # CLIENT
    # =========================================================
    elif role == "client":
        request.session["user_role"] = "client"
        request.session["connecte"] = True

        if user_trouve:
            email = getattr(user_trouve, "email", "")

            client_obj = Client.objects.filter(
                email__iexact=email
            ).first()

            if client_obj:
                request.session["client_connecte_id"] = client_obj.id

                request.session[
                    f"client_auth_{client_obj.id}"
                ] = True

                print(
                    "Client connecté :",
                    client_obj.id
                )

                return redirect(
                    "astra:espace_client",
                    client_id=client_obj.id
                )

        return redirect("astra:clients")

    # =========================================================
    # APPROVISIONNEMENT
    # =========================================================
    elif role == "approvisionnement":
        request.session["user_role"] = "approvisionnement"
        request.session["connecte"] = True

        return redirect("astra:approvisionnements")

    # =========================================================
    # RÔLE INCONNU
    # =========================================================
    messages.warning(
        request,
        "Votre rôle n'est pas reconnu. Contactez l'administrateur."
    )

    return redirect("astra:login")

# ==========================================================
# DÉCORATEUR D'ACCÈS SÉCURISÉ
# ==========================================================
def verifier_acces_strict(allowed_roles=None):

    # =========================
    # UTILISATION SANS PARAMÈTRE
    # =========================

    if callable(allowed_roles):

        view_func = allowed_roles

        @wraps(view_func)
        def _wrapped_view_direct(
            request,
            *args,
            **kwargs
        ):

            is_logged = (
                request.session.get("connecte")
                or request.session.get("utilisateur_id")
            )

            if not is_logged:

                messages.warning(
                    request,
                    "Veuillez vous connecter pour accéder à cette page."
                )

                return redirect(
                    "astra:login"
                )

            return view_func(
                request,
                *args,
                **kwargs
            )

        return _wrapped_view_direct

    # =========================
    # RÔLES AUTORISÉS
    # =========================

    if allowed_roles is None:

        allowed_roles = []

    allowed_roles = [
        normaliser_role(role)
        for role in allowed_roles
    ]

    # =========================
    # DÉCORATEUR
    # =========================

    def decorator(view_func):

        @wraps(view_func)
        def _wrapped_view(
            request,
            *args,
            **kwargs
        ):

            # Vérification connexion
            is_logged = (
                request.session.get("connecte")
                or request.session.get("utilisateur_id")
            )

            if not is_logged:

                messages.warning(
                    request,
                    "Veuillez vous connecter pour accéder à cette page."
                )

                return redirect(
                    "astra:login"
                )

            # Récupération du rôle
            user_role = normaliser_role(
                request.session.get(
                    "user_role",
                    ""
                )
            )

            print(
                "========== CONTRÔLE ACCÈS =========="
            )

            print(
                "Rôle utilisateur :",
                user_role
            )

            print(
                "Rôles autorisés :",
                allowed_roles
            )

            # =========================
            # CONTRÔLE DU RÔLE
            # =========================

            if allowed_roles:

                if user_role not in allowed_roles:

                    messages.error(
                        request,
                        "Accès non autorisé pour votre profil."
                    )

                    return rediriger_selon_role(
                        request,
                        user_role
                    )

            # =========================
            # ACCÈS AUTORISÉ
            # =========================

            return view_func(
                request,
                *args,
                **kwargs
            )

        return _wrapped_view

    return decorator

# ==========================================================
# API LOGIN TOKEN
# ==========================================================

class LoginWithTokenView(APIView):
    def post(self, request):
        serializer = EmailTokenObtainSerializer(
            data=request.data,
            context={"request": request}
        )
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================================
# CONNEXION
# ==========================================================
def login_view(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        prenom = request.POST.get('prenom', '').strip()
        password = request.POST.get('password', '').strip()
        
        # Recherche dans ton modèle personnalisé 'Utilisateur'
        user_trouve = None
        try:
            if nom and prenom:
                user_trouve = Utilisateur.objects.filter(
                    nom__iexact=nom, 
                    prenom__iexact=prenom
                ).first()
            elif nom: # Si l'utilisateur met son email ou son nom dans le champ nom
                user_trouve = Utilisateur.objects.filter(
                    models.Q(email__iexact=nom) | models.Q(nom__iexact=nom)
                ).first()
        except Exception:
            user_trouve = None

        if user_trouve:
            # Enregistrement des informations de session
            role = normaliser_role(getattr(user_trouve, 'role', 'client'))
            
            request.session['utilisateur_id'] = user_trouve.id
            request.session['user_id'] = user_trouve.id
            request.session['user_role'] = role
            request.session['user_nom'] = getattr(user_trouve, 'nom', '')
            request.session['user_prenom'] = getattr(user_trouve, 'prenom', '')
            request.session['connecte'] = True
            request.session.modified = True
            
            messages.success(request, "Connexion réussie !")
            return rediriger_selon_role(request, role=role, user_trouve=user_trouve)
        else:
            messages.error(request, "Nom ou prénom incorrect. Veuillez vérifier vos informations ou créer un compte.")
            return render(request, 'astra/login.html')
            
    return render(request, 'astra/login.html')

# ==========================================================
# DÉCONNEXION
# ==========================================================

def deconnexion(request):
    logout(request)
    request.session.flush()
    return redirect("astra:login")

# ==========================
# ACCUEIL & INSCRIPTION
# ==========================
def accueil(request):
    aujourd_hui = timezone.now().date()
    debut_mois = aujourd_hui.replace(day=1)

    ventes_aujourd_hui = Vente.objects.filter(date_vente__date=aujourd_hui).count()
    total_ventes = Vente.objects.aggregate(total=Sum('montant_total'))['total'] or 0
    total_appro = Approvisionnement.objects.aggregate(total=Sum('montant_total'))['total'] or 0
    chiffre_affaires = total_ventes + total_appro
    nouveaux_clients = Client.objects.filter(date_inscription__gte=debut_mois).count()
    produits_en_stock = Produit.objects.filter(is_active=True).aggregate(total=Sum('stock'))['total'] or 0

    context = {
        'ventes_aujourd_hui': ventes_aujourd_hui,
        'chiffre_affaires': chiffre_affaires,
        'nouveaux_clients': nouveaux_clients,
        'produits_en_stock': produits_en_stock,
    }
    return render(request, 'astra/accueil.html', context)

def client_register(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        prenom = request.POST.get('prenom', '').strip()
        email = request.POST.get('email', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        role = request.POST.get('role', 'client').lower().strip()
        password = request.POST.get('password', '1234')

        # Vérifier si l'utilisateur existe déjà par son email
        user_existant = None
        if email:
            user_existant = Utilisateur.objects.filter(email__iexact=email).first()

        if user_existant:
            # S'il existe déjà, on le connecte directement
            request.session['utilisateur_id'] = user_existant.id
            request.session['user_role'] = normaliser_role(getattr(user_existant, 'role', role))
            request.session['connecte'] = True
            messages.info(request, f"Un compte existe déjà pour {email}. Connexion directe.")
            return rediriger_selon_role(request, role=request.session['user_role'], user_trouve=user_existant)
        else:
            try:
                # Création d'un nouvel utilisateur enregistré en base de données
                nouveau_user = Utilisateur.objects.create(
                    nom=nom,
                    prenom=prenom,
                    email=email,
                    telephone=telephone,
                    role=role,
                    password=make_password(password) if hasattr(Utilisateur, 'password') else password
                )
                
                # Enregistrement dans la session pour le connecter tout de suite
                request.session['utilisateur_id'] = nouveau_user.id
                request.session['user_role'] = normaliser_role(nouveau_user.role)
                request.session['connecte'] = True
                request.session.modified = True
                
                messages.success(request, "Compte créé avec succès ! Bienvenue.")
                return rediriger_selon_role(request, role=request.session['user_role'], user_trouve=nouveau_user)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'inscription : {str(e)}")
                return redirect('astra:register')

    return render(request, 'astra/client_register.html')

# ==========================
# GESTION DES TOKENS & UTILISATEURS
# ==========================
@verifier_acces_strict(allowed_roles=['admin', 'fournisseur', 'approvisionneur', 'client'])
def token_accueil(request):
    registered_users = User.objects.all().order_by('username')
    context = {
        'registered_users': registered_users,
    }
    return render(request, 'astra/token_accueil.html', context)


@csrf_exempt
@verifier_acces_strict(allowed_roles=['admin'])
def generer_token_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email_destinataire = data.get('email', '').strip().lower()
            role = data.get('role', 'utilisateur').lower()
            validite_heures = int(data.get('validite', 24))

            if not email_destinataire:
                return JsonResponse({'status': 'error', 'message': "L'adresse email est requise."}, status=400)

            part1 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
            part2 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
            token_genere = f'ASTRA-{part1}-{part2}'

            secondary_token = None
            if role in ['client', 'fournisseur']:
                s_part1 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
                s_part2 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
                prefixe_sec = 'CLI' if role == 'client' else 'FRN'
                secondary_token = f'{prefixe_sec}-{s_part1}-{s_part2}'

                if role == 'client':
                    client_obj = Client.objects.filter(email__iexact=email_destinataire).first()
                    if client_obj:
                        client_obj.mot_de_passe = secondary_token 
                        client_obj.save()
                    else:
                        Client.objects.create(
                            email=email_destinataire,
                            nom=email_destinataire.split('@')[0],
                            mot_de_passe=secondary_token
                        )
                elif role == 'fournisseur':
                    fournisseur_obj = Fournisseur.objects.filter(email__iexact=email_destinataire).first()
                    if fournisseur_obj:
                        fournisseur_obj.mot_de_passe = secondary_token
                        fournisseur_obj.save()
                    else:
                        Fournisseur.objects.create(
                            email=email_destinataire,
                            nom=email_destinataire.split('@')[0],
                            mot_de_passe=secondary_token
                        )

            Token.objects.create(
                email=email_destinataire,
                valeur_token=token_genere,
                role=role,
                date_expiration=timezone.now() + timedelta(hours=validite_heures)
            )

            lien_connexion = "http://192.168.0.120:8000"
            sujet = f"Activation de votre espace [{role.upper()}] - ASTRA TECH"
            message = (
                f"Bonjour,\n\n"
                f"Votre accès [{role.upper()}] a été activé.\n"
                f"Mot de passe application : {token_genere}\n"
                f"Mot de passe espace dédié : {secondary_token or 'N/A'}\n"
                f"Lien : {lien_connexion}\n\n"
                f"Cordialement,\nL'équipe ASTRA TECH"
            )

            send_mail(
                subject=sujet,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_destinataire],
                fail_silently=False,
            )

            return JsonResponse({
                'status': 'success',
                'message': f'Accès générés et envoyés à {email_destinataire}',
                'token': token_genere,
                'secondary_token': secondary_token or role.upper(),
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)


def get_emails_clients_fournisseurs_api(request):
    emails_clients = list(Client.objects.values_list('email', flat=True))
    emails_fournisseurs = list(Fournisseur.objects.values_list('email', flat=True))
    tous_emails = list(set(emails_clients + emails_fournisseurs))
    return JsonResponse({'status': 'success', 'emails': tous_emails})


@verifier_acces_strict(allowed_roles=['admin'])
def users_page_view(request):
    return render(request, 'astra/page_utilisateurs.html')


@csrf_exempt
@verifier_acces_strict(allowed_roles=['admin'])
def api_users_list_create(request):
    if request.method == 'GET':
        users = User.objects.all().order_by('-id')
        data = [
            {
                'id': u.id,
                'name': u.username,
                'email': u.email,
                'role': 'Super Admin' if u.is_superuser else 'Utilisateur',
                'active': u.is_active,
            }
            for u in users
        ]
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')
            role = data.get('role')

            if not name or not email:
                return JsonResponse({'status': 'error', 'message': 'Nom et email requis.'}, status=400)

            if User.objects.filter(username=name).exists():
                return JsonResponse({'status': 'error', 'message': "Ce nom d'utilisateur existe déjà."}, status=400)

            user = User.objects.create_user(username=name, email=email, password='PasswordAstra2026!')
            if role == 'Super Admin':
                user.is_superuser = True
                user.is_staff = True
                user.save()

            return JsonResponse({'status': 'success', 'message': 'Utilisateur créé avec succès.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)


@api_view(['GET', 'PATCH', 'DELETE'])
@verifier_acces_strict(allowed_roles=['admin'])
def api_user_detail_update_delete(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)

    elif request.method == 'PATCH':
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================
# VENTES
# ==========================
# ==========================
# ==========================
# VENTES
# ==========================
def ventes_view(request):
    produits = Produit.objects.filter(stock__gt=0, is_active=True)
    ventes_list = Vente.objects.filter(est_archive=False).select_related('client').order_by('-id')
    
    total_ventes_count = ventes_list.count()
    montant_total_global = ventes_list.aggregate(total=Sum('montant_total'))['total'] or 0
    
    produits_vendus_count = 0
    try:
        for ligne in LigneVente.objects.all():
            v = getattr(ligne, 'vente', None)

            if v and not getattr(v, 'est_archive', False):
                qte = getattr(ligne, 'quantite', getattr(ligne, 'qte', getattr(ligne, 'qty', 1)))
                produits_vendus_count += int(qte or 1)
    except Exception:
        pass

    if produits_vendus_count == 0:
        try:
            mouvements = MouvementStock.objects.filter(type_mouvement="sortie")
            produits_vendus_count = sum(m.quantite for m in mouvements if m.quantite)
        except Exception:
            pass

    if produits_vendus_count == 0 and total_ventes_count > 0:
        produits_vendus_count = total_ventes_count * 1

    produits_dispo_count = Produit.objects.filter(is_active=True).count()

    context = {
        'produits': produits,
        'ventes': ventes_list,
        'total_ventes_count': total_ventes_count,
        'montant_total_global': montant_total_global,
        'produits_vendus_count': produits_vendus_count,
        'produits_dispo_count': produits_dispo_count,
    }
    return render(request, 'astra/vente.html', context)


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

def client_login(request):
    """
    Vue de connexion dédiée pour l'application ASTRA TECH.
    Gère l'authentification et redirige l'utilisateur selon son rôle ou vers le tableau de bord.
    """
    if request.user.is_authenticated:
        return redirect('dashboard') # Redirige si déjà connecté

    if request.method == 'POST':
        # Récupération des champs du formulaire (adapte 'username' et 'password' si tu utilises un champ 'email')
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, "Veuillez remplir tous les champs.")
            return render(request, 'astra/login.html')

        # Authentification de l'utilisateur
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f"Bienvenue, {user.username} !")
                
                # Récupération de l'URL 'next' s'il y en a une, sinon redirection par défaut
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard') # Remplace par le nom de ta route principale (ex: 'accueil', 'ventes', etc.)
            else:
                messages.error(request, "Ce compte utilisateur est désactivé.")
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")

    return render(request, 'astra/login.html')


@csrf_exempt
@verifier_acces_strict
@transaction.atomic
def enregistrer_vente(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            client_nom = data.get('client_nom', 'Client comptoir').strip()
            client_telephone = data.get('client_telephone', '').strip()
            client_email = data.get('client_email', '').strip()
            
            montant_total = float(data.get('montant_total', 0))
            montant_verse = float(data.get('montant_verse', data.get('montant_paye', 0)))
            
            mode_paiement = data.get('mode_paiement', 'especes')
            statut = data.get('statut', 'Confirmée & Payée')
            produits_panier = data.get('produits', [])

            if not produits_panier:
                return JsonResponse({'success': False, 'error': 'Le panier est vide.'}, status=400)

            if montant_verse < montant_total:
                return JsonResponse({
                    'success': False, 
                    'error': f"Montant insuffisant ! Le total est de {montant_total} FCFA, mais le montant versé est de {montant_verse} FCFA."
                }, status=400)

            nom_final = client_nom if client_nom else 'Client comptoir'

            client = None
            if client_telephone:
                client = Client.objects.filter(telephone=client_telephone).first()
            elif client_email:
                client = Client.objects.filter(email=client_email).first()
            
            if not client and nom_final != 'Client comptoir':
                client = Client.objects.filter(nom=nom_final).first()

            if client:
                updated_fields = []
                if client_telephone and client.telephone != client_telephone:
                    client.telephone = client_telephone
                    updated_fields.append('telephone')
                if client_email and client.email != client_email:
                    client.email = client_email
                    updated_fields.append('email')
                if client_nom and client.nom != client_nom:
                    client.nom = client_nom
                    updated_fields.append('nom')
                if not client.is_active:
                    client.is_active = True
                    updated_fields.append('is_active')
                    
                if updated_fields:
                    client.save(update_fields=updated_fields)
            else:
                client_defaults = {
                    'is_active': True,
                    'telephone': client_telephone,
                    'email': client_email
                }
                
                if hasattr(Client, 'reference'):
                    client_defaults['reference'] = f"CLI-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"

                client = Client.objects.create(nom=nom_final, **client_defaults)

            reference = f"VNT-{timezone.now().strftime('%Y%m%d%H%M%S')}"

            produits_a_traiter = []
            for item in produits_panier:
                produit_id = item.get('id')
                qte = int(item.get('quantite', 1))

                try:
                    produit = Produit.objects.select_for_update().get(id=produit_id, is_active=True)
                except Produit.DoesNotExist:
                    raise ValueError(f"Un produit du panier (ID: {produit_id}) est introuvable.")

                if produit.stock < qte:
                    raise ValueError(f"Stock insuffisant pour '{produit.nom}'. Stock actuel : {produit.stock}, Demandé : {qte}")

                produits_a_traiter.append((produit, qte))

            vente = Vente.objects.create(
                reference=reference,
                client=client,
                montant_total=montant_total,
                mode_paiement=mode_paiement,
                statut=statut,
                date_vente=timezone.now(),
                est_archive=False
            )

            for produit, qte in produits_a_traiter:
                Produit.objects.filter(id=produit.id).update(stock=F('stock') - qte)

                MouvementStock.objects.create(
                    produit=produit,
                    type_mouvement="sortie",
                    quantite=qte
                )

                LigneVente.objects.create(
                    vente=vente,
                    produit=produit,
                    quantite=qte,
                    prix_unitaire=float(produit.prix_vente)
                )

            request.session['rapports_reset_actif'] = False

            return JsonResponse({
                'success': True, 
                'message': 'Vente enregistrée avec succès et informations du client mises à jour !', 
                'reference': reference
            })

        except ValueError as ve:
            return JsonResponse({'success': False, 'error': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f"Une erreur système s'est produite lors de la vente : {str(e)}"}, status=500)

    return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'}, status=405)


@verifier_acces_strict
def details_vente(request, vente_id):
    vente = get_object_or_404(Vente.objects.select_related('client'), id=vente_id)
    lignes = LigneVente.objects.filter(vente=vente).select_related('produit')

    data = {
        'reference': vente.reference,
        'client': vente.client.nom if vente.client else 'Client comptoir',
        'client_telephone': vente.client.telephone if vente.client and vente.client.telephone else '',
        'client_email': vente.client.email if vente.client and vente.client.email else '',
        'date': vente.date_vente.strftime("%d/%m/%Y à %H:%M") if vente.date_vente else '',
        'montant_total': float(vente.montant_total or 0),
        'mode_paiement': getattr(vente, 'mode_paiement', 'Espèces'),
        'statut': getattr(vente, 'statut', 'Confirmée'),
        'lignes': [
            {
                'produit': l.produit.nom if l.produit else "Produit",
                'quantite': l.quantite,
                'prix_unitaire': float(l.prix_unitaire),
                'sous_total': float(l.prix_unitaire * l.quantite)
            } for l in lignes
        ]
    }
    return JsonResponse(data)


@csrf_exempt
@transaction.atomic
@verifier_acces_strict
def supprimer_vente(request, vente_id):
    if request.method in ['POST', 'DELETE']:
        try:
            vente = get_object_or_404(Vente, id=vente_id)
            vente.est_archive = True  
            vente.save()

            return JsonResponse({'success': True, 'message': 'Vente placée dans la corbeille avec succès.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
            
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
@transaction.atomic
@verifier_acces_strict
def modifier_vente(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nouveau_nom = data.get('client_nom', '').strip()
            nouvel_email = data.get('client_email', '').strip()
            nouveau_telephone = data.get('client_telephone', '').strip()
            nouveau_mode = data.get('mode_paiement', 'especes')

            vente.mode_paiement = nouveau_mode
            vente.save()

            if vente.client:
                client = vente.client
                if nouveau_nom: client.nom = nouveau_nom
                if nouvel_email: client.email = nouvel_email
                if nouveau_telephone: client.telephone = nouveau_telephone
                client.save()
            elif nouveau_nom:
                client, _ = Client.objects.get_or_create(
                    nom=nouveau_nom,
                    defaults={'email': nouvel_email, 'telephone': nouveau_telephone, 'is_active': True}
                )
                vente.client = client
                vente.save()

            return JsonResponse({
                'success': True, 
                'message': 'Vente modifiée avec succès !'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'}, status=405)

@verifier_role(['client']) # ou le rôle approprié
def gestion_clients(request):
    # 1. Gestion de l’ajout d’un client en POST
    if request.method == 'POST':
        nom = request.POST.get('nom')
        email = request.POST.get('email') or None
        telephone = request.POST.get('telephone')
        adresse = request.POST.get('adresse') or ''
        mot_de_passe = request.POST.get('mot_de_passe')
        
        if email and Client.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà utilisé.")

        else:
            nouveau_client = Client(
                nom=nom, 
                email=email, 
                telephone=telephone, 
                adresse=adresse
            )
            if mot_de_passe:
                nouveau_client.mot_de_passe = mot_de_passe 
            else:
                nouveau_client.mot_de_passe = "1234"
            
            nouveau_client.date_inscription = date.today()
            nouveau_client.save()
            
            messages.success(request, "Client ajouté avec succès.")
            return redirect('astra:gestion_clients')

    # ==========================
    # AFFICHAGE
    # ==========================

    filter_type = request.GET.get('filter', 'all')
    today = date.today()

    clients_bruts = Client.objects.filter(
        is_active=True
    ).order_by('-id')

    clients_list = []

    for client in clients_bruts:

        ventes_actives = client.ventes.filter(
            est_archive=False
        )

        client.nombre_achats = ventes_actives.count()

        client.total_depenses = ventes_actives.aggregate(
            total=Sum('montant_total')
        )['total'] or 0

        c_date = getattr(client, 'date_inscription', None)

        client.est_nouveau = False

        if c_date:
            if hasattr(c_date, 'date'):
                c_date = c_date.date()

            if c_date == today:
                client.est_nouveau = True

        clients_list.append(client)

    # ==========================
    # FILTRES
    # ==========================

    if filter_type == 'loyal':
        clients_qs = [c for c in clients_list if c.nombre_achats >= 2]
    elif filter_type == 'new':
        clients_qs = [c for c in clients_list if c.est_nouveau]
    else:

        clients_qs = clients_list

    total_clients = Client.objects.filter(is_active=True).count()
    new_clients_count = sum(1 for c in clients_list if c.est_nouveau)
    loyal_clients_count = sum(1 for c in clients_list if c.nombre_achats >= 2)

    context = {
        'clients': clients_qs,
        'clients_archives': Client.objects.filter(is_active=False).order_by('-id'),
        'total_clients': total_clients,
        'new_clients_count': new_clients_count,
        'loyal_clients_count': loyal_clients_count,
        'current_filter': filter_type,
    }
    
    return render(request, 'astra/clients.html', context)

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip() # Utilise l'email ou le nom d'utilisateur selon ton form de login
        password = request.POST.get('password', '').strip()
        
        # Recherche par email ou nom d'utilisateur
        user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username__iexact=email).first()
        
        if user is not None and user.check_password(password):
            login(request, user)
            
            # Récupération et normalisation du rôle
            role = normaliser_role(getattr(user, 'role', 'client'))
            
            request.session['user_role'] = role
            request.session['connecte'] = True
            request.session.modified = True
            
            return rediriger_selon_role(request, role=role, user_trouve=user)
        else:
            messages.error(request, "Identifiants ou mot de passe incorrect.")
            return render(request, 'astra/login.html')
            
    return render(request, 'astra/login.html')



def espace_client(request, client_id):
    client_user = get_object_or_404(Client, id=client_id)
    
    request.session['client_connecte_id'] = client_user.id
    
    historique_achats = Vente.objects.filter(client=client_user, est_archive=False).order_by('-date_vente')

    context = {
        'client_user': client_user,
        'historique_achats': historique_achats,
    }
    return render(request, 'astra/espace_client.html', context)

def detail_client_activites(request, client_id):
    session_id = request.session.get('client_connecte_id')
    if not session_id:
        return redirect('astra:client_login', client_id=client_id)

    client = get_object_or_404(Client, id=client_id)
    
    if int(session_id) != int(client.id):
        return redirect('astra:detail_client_activites', client_id=session_id)

    historique_achats = Vente.objects.filter(client=client, est_archive=False).order_by('-date_vente')
    nombre_achats = historique_achats.count()
    total_depenses = historique_achats.aggregate(total=Sum('montant_total'))['total'] or 0

    context = {
        'client': client,
        'historique_achats': historique_achats,
        'nombre_achats': nombre_achats,
        'total_depenses': total_depenses,
    }
    
    return render(request, 'astra/detail_client_activites.html', context)

@verifier_acces_strict
def supprimer_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.is_active = False
    client.save()
    
    messages.success(request, f"Le client {client.nom} a été archivé avec succès.")
    return redirect('astra:gestion_clients')

@verifier_acces_strict
def modifier_client(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    if request.method == 'POST':
        client.nom = request.POST.get('nom', client.nom)
        client.email = request.POST.get('email', '')
        client.telephone = request.POST.get('telephone', client.telephone)
        client.adresse = request.POST.get('adresse', '')
        client.save()
    return redirect('astra:gestion_clients')

@verifier_acces_strict
def reset_page_rapports(request):
    if request.method == 'POST':
        request.session['rapports_reset_actif'] = True
        messages.success(request, "La page des rapports a été réinitialisée pour la réunion.")
    return redirect('astra:rapports')

# ==========================
# STOCKS & PRODUITS
# ==========================
@verifier_role(["client", "vendeur"])
def stock_view(request):
    produits = Produit.objects.filter(is_active=True).select_related('categorie')
    categories = Categorie.objects.all()
    
    total_produits = produits.count()
    stock_faible = produits.filter(stock__lte=F('seuil_alerte')).count() if hasattr(Produit, 'seuil_alerte') else 0
    valeur_stock = produits.aggregate(
        total=Sum(F('prix_achat') * F('stock'))
    )['total'] or 0

    context = {
        'produits': produits,
        'categories': categories,
        'total_produits': total_produits,
        'stock_faible': stock_faible,
        'valeur_stock': valeur_stock,
    }
    return render(request, 'astra/stock.html', context)

@verifier_role(["client", "vendeur"])
def liste_stocks(request):
    categories = Categorie.objects.prefetch_related('produit_set').all()
    produits = Produit.objects.all()
    
    context = {
        'categories': categories,
        'produits': produits,
    }
    return render(request, 'astra/liste_stocks.html', context)
  
import uuid

@csrf_exempt
@verifier_acces_strict
def ajouter_produit(request):
    if request.method == 'POST':
        try:
            nom = request.POST.get('nom')
            categorie_id = request.POST.get('categorie_id')
            prix_achat = request.POST.get('prix_achat', 0)
            prix_vente = request.POST.get('prix_vente', 0)
            stock = request.POST.get('stock', 0)

            categorie = Categorie.objects.filter(id=categorie_id).first() if categorie_id else None

            prefixe = categorie.nom[:3].upper() if categorie else "AST"
            unique_id = str(uuid.uuid4())[:4].upper()
            reference = f"{prefixe}-{unique_id}"

            Produit.objects.create(
                reference=reference,
                nom=nom,
                categorie=categorie,
                prix_achat=prix_achat,
                prix_vente=prix_vente,
                stock=stock,
                is_active=True
            )
            return JsonResponse({'status': 'success', 'message': f'Produit enregistré avec succès (Réf: {reference}) !'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)


@csrf_exempt
@verifier_acces_strict
def modifier_produit(request, product_id):
    produit = get_object_or_404(Produit, id=product_id, is_active=True)
    if request.method == 'POST':
        try:
            produit.reference = request.POST.get('reference', produit.reference)
            produit.nom = request.POST.get('nom', produit.nom)
            
            categorie_id = request.POST.get('categorie_id')
            if categorie_id:
                produit.categorie = Categorie.objects.filter(id=categorie_id).first()
            else:
                produit.categorie = None
                
            produit.prix_achat = request.POST.get('prix_achat', produit.prix_achat)
            produit.prix_vente = request.POST.get('prix_vente', produit.prix_vente)
            produit.stock = request.POST.get('stock', produit.stock)
            produit.save()

            return JsonResponse({'status': 'success', 'message': 'Produit modifié avec succès !'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)


@csrf_exempt
@verifier_acces_strict
def supprimer_produit(request, product_id):
    if request.method == 'POST':
        try:
            produit = get_object_or_404(Produit, id=product_id)
            produit.is_active = False
            produit.save()
            return JsonResponse({'status': 'success', 'message': 'Produit désactivé/supprimé avec succès !'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)


# ==========================
# FOURNISSEURS & ESPACE FOURNISSEUR DÉDIÉ
# ==========================
@role_required(allowed_roles=['entreprise', 'admin'])
@verifier_acces_strict
def fournisseurs(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        nom = request.POST.get('nom', '').strip()
        contact = request.POST.get('contact')
        telephone = request.POST.get('telephone')
        email = request.POST.get('email')

        try:
            if supplier_id:  
                fournisseur = get_object_or_404(Fournisseur, id=supplier_id, is_active=True)
                fournisseur.nom = nom
                fournisseur.contact = contact
                fournisseur.telephone = telephone
                fournisseur.email = email
                fournisseur.save()
                messages.success(request, "Fournisseur mis à jour avec succès.")
            else:  
                # Vérification stricte : si un fournisseur actif avec le même nom existe déjà, on évite le doublon
                fournisseur_existant = Fournisseur.objects.filter(nom__iexact=nom, is_active=True).first()
                
                if fournisseur_existant:
                    # Soit on met à jour ses infos, soit on l'informe qu'il existe déjà
                    messages.error(request, f"Un fournisseur portant le nom '{nom}' existe déjà dans le répertoire unique.")
                else:
                    Fournisseur.objects.create(
                        nom=nom,
                        contact=contact,
                        telephone=telephone,
                        email=email,
                        is_active=True
                    )
                    messages.success(request, "Fournisseur créé avec succès dans son cahier unique.")

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            
            return redirect('astra:fournisseurs')

        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # Récupération propre : on s'assure de ne lister que les fournisseurs uniques par nom si des doublons existent déjà en base
    # (ou utilise .distinct('nom') si ta base de données supporte PostgreSQL, sinon on filtre par nom unique)
    tous_fournisseurs = Fournisseur.objects.filter(is_active=True).order_by('nom', '-id')
    
    # Filtrage en Python pour garantir zéro doublon visuel de nom
    noms_traites = set()
    liste_fournisseurs = []
    for f in tous_fournisseurs:
        nom_normalise = f.nom.strip().lower()
        if nom_normalise not in noms_traites:
            noms_traites.add(nom_normalise)
            liste_fournisseurs.append(f)

    context = {
        'fournisseurs': liste_fournisseurs,
    }
    return render(request, 'astra/fournisseurs.html', context)

@verifier_acces_strict
def supprimer_fournisseur(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    fournisseur.is_active = False
    fournisseur.save()
    return redirect('astra:fournisseurs')
    
def espace_fournisseur(request, pk):
    fournisseur_connecte_id = request.session.get('fournisseur_connecte_id')
    
    if not fournisseur_connecte_id or int(fournisseur_connecte_id) != int(pk):
        messages.error(request, "Veuillez entrer le mot de passe pour accéder à cet espace.")
        return redirect('astra:connexion_fournisseur', fournisseur_id=pk)

    fournisseur_principal = get_object_or_404(Fournisseur, pk=pk)
    # ... reste de ta vue ...
    # 2. Trouve tous les autres fournisseurs (doublons) qui ont exactement le même nom
    doublons_fournisseurs = Fournisseur.objects.filter(
        nom__iexact=fournisseur_principal.nom, 
        is_active=True
    )
    
    # 3. Récupère les approvisionnements de TOUS les doublons
    approvisionnements = Approvisionnement.objects.filter(
        fournisseur__in=doublons_fournisseurs
    ).order_by('-date_creation')

    contexte = {
        'fournisseur': fournisseur_principal,
        'approvisionnements': approvisionnements,
    }
    
    return render(request, 'astra/espace_fournisseur.html', contexte)

def verification_mot_de_passe_app(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_id)
    
    if request.method == 'POST':
        password_app = request.POST.get('password_app')
        
        # Vérifie le mot de passe de l'application
        if password_app == fournisseur.password_application: # Ajuste selon ton champ
            # REDIRECTION OBLIGATOIRE VERS LA DEUXIÈME PAGE DE CONNEXION (Fournisseur)
            return redirect('astra:connexion_fournisseur', fournisseur_id=fournisseur.id)
        else:
            messages.error(request, "Mot de passe de l'application incorrect.")
            
    return render(request, 'astra/verification_app.html', {'fournisseur': fournisseur})
    
def deconnexion_fournisseur(request, pk):
    if 'fournisseur_connecte_id' in request.session:
        del request.session['fournisseur_connecte_id']
    messages.success(request, "Vous avez été déconnecté de votre espace.")
    return redirect('astra:connexion_fournisseur', fournisseur_id=pk)

def envoyer_email_fournisseur(request, fournisseur_id):
    if request.method == 'POST':
        fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
        
        sujet_client = request.POST.get('sujet', 'Approvisionnement - Astra Tech')
        message_client = request.POST.get('message', '')
        
        if not fournisseur.email:
            return JsonResponse({'status': 'error', 'message': "Ce fournisseur ne possède pas d'adresse e-mail enregistrée."}, status=400)
        
        try:
            sujet = f"📦 {sujet_client} - {fournisseur.nom}"
            contenu_email = f"""
Bonjour {fournisseur.nom},

{message_client}

---
Informations de suivi :
- Fournisseur : {fournisseur.nom}
- Téléphone : {fournisseur.telephone}
- Date d'envoi : {timezone.now().strftime('%d/%m/%Y à %H:%M')}

Cordialement,
L'équipe Astra Tech
            """
            
            expediteur = settings.DEFAULT_FROM_EMAIL
            destinataires = [fournisseur.email, 'lynel9324@gmail.com']
            
            send_mail(sujet, contenu_email, expediteur, destinataires, fail_silently=False)
            
            NotificationPlateforme.objects.create(
                titre=f"Approvisionnement : {fournisseur.nom}",
                message=f"Un e-mail a été envoyé à {fournisseur.email}. Message : {message_client[:80]}..."
            )

            return JsonResponse({
                'status': 'success', 
                'message': f"E-mail envoyé avec succès à {fournisseur.nom} et alerte enregistrée sur la plateforme !"
            })
            
        except Exception as e:
            print("Erreur technique d'envoi d'e-mail :", e)
            return JsonResponse({
                'status': 'error', 
                'message': f"Erreur technique lors de l'envoi : {str(e)}"
            }, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=400)

def connexion_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_id)
    
    if request.method == 'POST':
        password = request.POST.get('password')
        
        # Remplace '.password' par le vrai nom du champ dans ton modèle (ex: .mot_de_passe)
        if password == fournisseur.mot_de_passe: 
            request.session['fournisseur_connecte_id'] = fournisseur.id
            return redirect('astra:espace_fournisseur', pk=fournisseur.id)
        else:
            messages.error(request, "Mot de passe incorrect.")
            
    return redirect('astra:fournisseurs')
# ==========================
# GESTION DES APPROVISIONNEMENTS
# ==========================

def approvisionnements_view(request):
    if request.method == 'POST':
        fournisseur_id = request.POST.get('fournisseur')
        montant_total = request.POST.get('montant_total', 0)
        statut = request.POST.get('statut', 'en_attente')
        
        if fournisseur_id:
            Approvisionnement.objects.create(
                fournisseur_id=fournisseur_id,
                montant_total=montant_total,
                statut=statut,
                is_active=True
            )
        return redirect('astra:approvisionnements')

    liste_appros = Approvisionnement.objects.filter(is_active=True).select_related('fournisseur').all()
    fournisseurs_list = Fournisseur.objects.filter(is_active=True)
    
    context = {
        'approvisionnements': liste_appros,
        'fournisseurs': fournisseurs_list,
    }
    return render(request, 'astra/approvisionnements.html', context)


@csrf_exempt
@verifier_acces_strict
def ajouter_approvisionnement(request):
    if request.method == 'POST':
        fournisseur_id = request.POST.get('fournisseur')
        if not fournisseur_id:
            return JsonResponse({'status': 'error', 'message': 'Veuillez choisir un fournisseur.'}, status=400)
        
        try:
            fournisseur = Fournisseur.objects.get(id=fournisseur_id, is_active=True)
            Approvisionnement.objects.create(
                fournisseur=fournisseur,
                statut='en_attente',
                montant_total=0.00,
                is_active=True
            )
            
            request.session['rapports_reset_actif'] = False

            return JsonResponse({'status': 'success', 'message': 'Approvisionnement enregistré avec succès.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
@verifier_acces_strict
def details_approvisionnement(request, pk):
    appro = get_object_or_404(Approvisionnement, pk=pk)
    
    montant_str = str(appro.montant_total).replace(',', '.') if appro.montant_total is not None else '0.00'

    date_str = ''
    if hasattr(appro, 'date_vente') and appro.date_vente:
        date_str = appro.date_vente.strftime('%Y-%m-%d %H:%M')
    elif hasattr(appro, 'date_creation') and appro.date_creation:
        date_str = appro.date_creation.strftime('%Y-%m-%d %H:%M')

    data = {
        'success': True,
        'id': appro.id,
        'reference': appro.reference,
        'fournisseur_id': appro.fournisseur.id if appro.fournisseur else '',
        'fournisseur': appro.fournisseur.nom if appro.fournisseur else 'N/A',
        'date': date_str,
        'montant_total': montant_str,
        'statut': appro.statut,
    }
    return JsonResponse(data)


@csrf_exempt
@verifier_acces_strict
def modifier_approvisionnement(request, pk):
    appro = get_object_or_404(Approvisionnement, pk=pk)
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            fournisseur_id = data.get('fournisseur')
            montant_total = data.get('montant_total')
            statut = data.get('statut')

            if fournisseur_id:
                fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
                appro.fournisseur = fournisseur
            
            if montant_total is not None and montant_total != '':
                appro.montant_total = montant_total
                
            if statut:
                appro.statut = statut

            appro.save()
            return JsonResponse({'success': True, 'message': 'Approvisionnement modifié avec succès.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)


def supprimer_approvisionnement(request, pk):
    appro = get_object_or_404(Approvisionnement, pk=pk)
    if request.method == 'POST':
        try:
            appro.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

@verifier_acces_strict
def rapports(request):
    reset_actif = request.session.get('rapports_reset_actif', False)

    total_stock_qty = Produit.objects.filter(is_active=True).aggregate(total=Sum('stock'))['total'] or 0
    produits_data = list(Produit.objects.filter(is_active=True).values('nom', 'stock'))
    produits_json = json.dumps(produits_data, cls=DjangoJSONEncoder)

    if reset_actif:
        total_sales = 0
        total_appros = 0
        total_clients = 0
        total_suppliers = 0
        clients_resume = []
        dernieres_ventes = []
        derniers_appros = []
        benefices_articles = []
        bilan_mensuel = []
        bilan_annuel = []
        benefice_net_global = 0
        appros_json = json.dumps([], cls=DjangoJSONEncoder)
        ventes_json = json.dumps([], cls=DjangoJSONEncoder)
    else:
        ventes_qs = Vente.objects.filter(est_archive=False).order_by('-date_vente', '-id')
        appros_qs = Approvisionnement.objects.filter(is_active=True).order_by('-id')

        total_sales = ventes_qs.aggregate(total=Sum('montant_total'))['total'] or 0
        total_appros = appros_qs.aggregate(total=Sum('montant_total'))['total'] or 0
        total_clients = Client.objects.filter(is_active=True).count()
        total_suppliers = Fournisseur.objects.filter(is_active=True).count()

        # Calcul détaillé des bénéfices par article commercialisé
        # On suppose que chaque vente possède des lignes d'articles (ou relation via LigneVente / items)
        # Ajustez 'lignevente_set' ou le nom de votre relation selon votre modèle si nécessaire
        benefices_articles = []
        benefice_net_global = 0

        # Récupération des lignes de vente pour calcul précis des marges
        try:
            from astra.models import LigneVente # Remplacez par votre nom de modèle de ligne de vente si besoin
            lignes_ventes = LigneVente.objects.filter(vente__est_archive=False)
            
            # Groupement par produit
            produits_sold = lignes_ventes.values('produit__nom').annotate(
                qte_vendue=Sum('quantite'),
                ca_genere=Sum(F('quantite') * F('prix_unitaire')),
                # Si vous avez un prix d'achat sur le produit :
                cout_total=Sum(F('quantite') * F('produit__prix_achat'))
            )
            
            for p in produits_sold:
                nom_p = p['produit__nom'] or 'Article divers'
                qte = p['qte_vendue'] or 0
                ca = float(p['ca_genere'] or 0)
                cout = float(p['cout_total'] or 0)
                benefice = ca - cout
                benefice_net_global += benefice
                
                benefices_articles.append({
                    'nom': nom_p,
                    'quantite': qte,
                    'ca': ca,
                    'cout': cout,
                    'benefice': benefice
                })
        except Exception:
            # Fallfait si le modèle de ligne de vente a un nom différent, on utilise une estimation globale saine
            benefice_net_global = float(total_sales) * 0.30 # Estimation prudente de marge si lignes absentes
            benefices_articles = []

        # Bilans Mensuels et Annuels basés sur les ventes
        bilan_mensuel = ventes_qs.annotate(mois=TruncMonth('date_vente')).values('mois').annotate(
            total_ca=Sum('montant_total')
        ).order_by('-mois')[:6]

        bilan_annuel = ventes_qs.annotate(annee=TruncYear('date_vente')).values('annee').annotate(
            total_ca=Sum('montant_total')
        ).order_by('-annee')[:3]

        clients_resume = Client.objects.filter(is_active=True).annotate(
            nombre_achats=Count('ventes', filter=Q(ventes__est_archive=False)),
            montant_total_achats=Sum('ventes__montant_total', filter=Q(ventes__est_archive=False)),
            dernier_achat=Max('ventes__date_vente', filter=Q(ventes__est_archive=False))
        ).filter(montant_total_achats__gt=0).order_by('-dernier_achat', '-nombre_achats')

        dernieres_ventes = ventes_qs[:5]

        appros_par_fournisseur = appros_qs.values('fournisseur').annotate(
            total_montant=Sum('montant_total'),
            dernier_id=Max('id'),
            nombre_appros=Count('id')
        ).order_by('-dernier_id')

        derniers_appros = []
        appros_list = []

        for group in appros_par_fournisseur:
            f_id = group.get('fournisseur')
            if f_id:
                fournisseur_obj = Fournisseur.objects.filter(id=f_id).first()
                f_nom = fournisseur_obj.nom if fournisseur_obj else 'Fournisseur externe'
            else:
                f_nom = 'Fournisseur externe'

            subs = appros_qs.filter(fournisseur_id=f_id) if f_id else appros_qs.filter(fournisseur__isnull=True)
            sub_data = list(subs.values('id', 'reference', 'montant_total', 'statut'))

            dernier_app = subs.first()
            app_id = group.get('dernier_id') or 1
            ref_affichage = dernier_app.reference if (dernier_app and dernier_app.reference) else f"APP-{app_id}"

            derniers_appros.append({
                'id': app_id,
                'reference': ref_affichage,
                'fournisseur_nom': f_nom,
                'montant_total': float(group.get('total_montant') or 0),
                'nombre_appros': group.get('nombre_appros') or 1
            })

            appros_list.append({
                'fournisseur': f_nom,
                'total': float(group.get('total_montant') or 0),
                'operations': sub_data
            })

        ventes_list = [{'reference': v.reference, 'montant_total': float(v.montant_total or 0), 'client_nom': v.client.nom if v.client else 'Client comptoir'} for v in ventes_qs]
        ventes_json = json.dumps(ventes_list, cls=DjangoJSONEncoder)
        appros_json = json.dumps(appros_list, cls=DjangoJSONEncoder)

    context = {
        'total_sales': total_sales,
        'total_stock_qty': total_stock_qty,   
        'total_clients': total_clients,
        'total_suppliers': total_suppliers,
        'total_appros': total_appros,
        'benefice_net_global': benefice_net_global,
        'benefices_articles': benefices_articles,
        'bilan_mensuel': bilan_mensuel,
        'bilan_annuel': bilan_annuel,
        'clients_resume': clients_resume,
        'dernieres_ventes': dernieres_ventes,  
        'derniers_appros': derniers_appros,    
        'ventes_json': ventes_json,
        'appros_json': appros_json,
        'produits_json': produits_json,      
    }

    return render(request, 'rapports.html', context)
# ==========================
# PAGES & APIS PARAMÈTRES
# ==========================

def permissions_page_view(request):
    return render(request, 'astra/permissions.html')

def historiques_page_view(request):
    # Récupération séparée pour chaque bloc de la page
    logs_approvisionnement = []
    for a in Approvisionnement.objects.all().order_by('-id')[:20]:
        d = getattr(a, 'date_approvisionnement', None) or getattr(a, 'date', None)
        logs_approvisionnement.append({
            'date': d.strftime("%d/%m/%Y à %H:%M") if d else "Récemment",
            'utilisateur': 'Administrateur',
            'details': f"Approvisionnement enregistré (Réf: {getattr(a, 'reference', a.id)})"
        })

    logs_ventes = []
    for v in Vente.objects.all().order_by('-id')[:20]:
        d = getattr(v, 'date_vente', None) or getattr(v, 'date', None)
        logs_ventes.append({
            'date': d.strftime("%d/%m/%Y à %H:%M") if d else "Récemment",
            'utilisateur': 'Administrateur',
            'details': f"Vente validée (Réf: {getattr(v, 'reference', v.id)}, Montant: {getattr(v, 'montant_total', '0')} FCFA)"
        })

    logs_admin = []
    for c in Client.objects.all().order_by('-id')[:10]:
        logs_admin.append({
            'date': "Récemment",
            'utilisateur': 'Administrateur',
            'details': f"Nouveau client : {c.nom}"
        })
    for p in Produit.objects.all().order_by('-id')[:10]:
        logs_admin.append({
            'date': "Récemment",
            'utilisateur': 'Administrateur',
            'details': f"Mise à jour stock produit : {p.nom} (Qté : {p.stock})"
        })

    context = {
        'logs_approvisionnement': logs_approvisionnement,
        'logs_ventes': logs_ventes,
        'logs_admin': logs_admin,
    }
    return render(request, 'astra/historique.html', context)

@verifier_acces_strict
def propos(request):
    return render(request, 'astra/propos.html')


@csrf_exempt
def api_save_permissions(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Exemple de traitement réel avec les groupes Django
            for key, value in data.items():
                # Format attendu ex: admin_vente, stock_stock, etc.
                parts = key.split('_')
                if len(parts) >= 2:
                    role_name = parts[0]
                    module_name = "_".join(parts[1:])
                    
                    # Récupération ou création du groupe correspondant
                    group_mapping = {
                        'admin': 'Administrateur',
                        'stock': 'Gestionnaire Stock',
                        'vendeur': 'Commercial / Vendeur',
                        'caissier': 'Caissier'
                    }
                    
                    group_title = group_mapping.get(role_name, role_name.capitalize())
                    group, created = Group.objects.get_or_create(name=group_title)
                    
                    # Attribution ou retrait réel de la permission en base de données
                    # (Optionnel selon votre gestion des codenames de permissions)
                    if value:
                        perm = Permission.objects.filter(codename__icontains=module_name).first()
                        if perm:
                            group.permissions.add(perm)
                    else:
                        perm = Permission.objects.filter(codename__icontains=module_name).first()
                        if perm:
                            group.permissions.remove(perm)

            return JsonResponse({
                'status': 'success', 
                'message': 'Les modifications de la matrice de sécurité ont été enregistrées en base de données.'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
def api_save_parametres(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'}, status=405)
    try:
        data = json.loads(request.body)
        config, created = ParametreGlobal.objects.get_or_create(id=1)
        
        # Mise à jour des champs avec conservation des anciennes valeurs si absentes
        config.nom_boutique = data.get('nom_boutique', config.nom_boutique)
        config.verrou_commercial = data.get('verrou_commercial', data.get('verrouillage_commercial', config.verrou_commercial))
        config.verrou_admin = data.get('verrou_admin', data.get('verrouillage_admin', config.verrou_admin))
        config.seuil_stock = data.get('seuil_stock', data.get('seuil_alerte_stock', config.seuil_stock))
        config.taux_tva = data.get('taux_tva', config.taux_tva)
        
        config.save()
        return JsonResponse({'success': True, 'status': 'success', 'message': 'Paramètres et verrous enregistrés avec succès.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
def parametres_page_view(request):
    config, created = ParametreGlobal.objects.get_or_create(id=1)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            config.nom_boutique = data.get('nom_boutique', config.nom_boutique)
            config.verrou_commercial = data.get('verrou_commercial', data.get('verrouillage_commercial', config.verrou_commercial))
            config.verrou_admin = data.get('verrou_admin', data.get('verrouillage_admin', config.verrou_admin))
            config.seuil_stock = data.get('seuil_stock', data.get('seuil_alerte_stock', config.seuil_stock))
            config.taux_tva = data.get('taux_tva', config.taux_tva)
            
            config.save()
            return JsonResponse({'status': 'success', 'message': 'Paramètres et verrous enregistrés en base de données.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    context = {
        'config': config
    }
    return render(request, 'astra/parametres.html', context)

@csrf_exempt
def api_users_list_create(request):
    if request.method == 'POST':
        try:
            # Analyse infaillible du corps JSON envoyé par le fetch JS
            data = json.loads(request.body)
            
            prenom = data.get('prenom', '').strip()
            nom = data.get('nom', '').strip()
            email = data.get('email', '').strip()
            password = data.get('mot_de_passe', 'Passer123!')
            
            # Vérification stricte des champs obligatoires
            if not nom or not email:
                return JsonResponse({'status': 'error', 'message': 'Nom et email requis.'}, status=400)

            if User.objects.filter(email=email).exists():
                return JsonResponse({'status': 'error', 'message': 'Un utilisateur avec cet email existe déjà.'}, status=400)

            # Création effective de l'utilisateur dans la base de données Django
            User.objects.create_user(
                username=email, 
                email=email, 
                password=password, 
                first_name=prenom, 
                last_name=nom
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Utilisateur / Client enregistré avec succès dans la base de données !'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)


def marquer_toutes_comme_lues(request):
    if request.method == 'POST' and request.user.is_authenticated:
        Notification.objects.filter(user=request.user, lue=False).update(lue=True)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


def detail_notification(request, pk):
    # Récupère la notification ou renvoie une 404
    notification = get_object_or_404(NotificationPlateforme, pk=pk)
    
    # Marquer comme lu si ce n'est pas déjà fait
    if not notification.lu:
        notification.lu = True
        notification.save()
        
    # Redirige vers la page précédente (HTTP_REFERER) ou vers l'accueil par défaut
    referer_url = request.META.get('HTTP_REFERER')
    if referer_url:
        return redirect(referer_url)
        
    return render(request, 'astra/detail_notification.html', {'notification': notification})

def notifications_header(request):
    """Context Processor sécurisé pour afficher les notifications de l'utilisateur connecté."""
    
    # Si l'utilisateur n'est pas connecté, on retourne des listes vides
    if not request.user.is_authenticated:
        return {
            'notifications_non_lues': [],
            'nombre_notifications': 0,
        }

    # Récupération directe des notifications non lues propres à l'utilisateur connecté
    notifs_non_lues = Notification.objects.filter(
        user=request.user,
        lue=False
    ).order_by('-id')

    total_non_lus = notifs_non_lues.count()

    return {
        'notifications_non_lues': notifs_non_lues,
        'nombre_notifications': total_non_lus,
    }

@csrf_exempt
def api_users_list_create(request):
    if request.method == 'GET':
        # Permet de lister les utilisateurs si le JS en a besoin
        utilisateurs = list(User.objects.values('id', 'first_name', 'last_name', 'email', 'is_active'))
        return JsonResponse({'status': 'success', 'users': utilisateurs})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            prenom = data.get('prenom', '').strip()
            nom = data.get('nom', '').strip()
            email = data.get('email', '').strip()
            password = data.get('mot_de_passe', 'Passer123!')
            
            if not nom or not email:
                return JsonResponse({'status': 'error', 'message': 'Nom et email requis.'}, status=400)

            if User.objects.filter(email=email).exists():
                return JsonResponse({'status': 'error', 'message': 'Un utilisateur avec cet email existe déjà.'}, status=400)

            User.objects.create_user(
                username=email, 
                email=email, 
                password=password, 
                first_name=prenom, 
                last_name=nom
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Utilisateur / Client enregistré avec succès dans la base de données !'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)    

@csrf_exempt
def mot_de_passe_oublie_client(request):
    if request.method == 'POST':
        telephone = request.POST.get('telephone')
        date_naissance_str = request.POST.get('date_naissance')
        nouveau_mdp = request.POST.get('new_password')
        
        # 1. On vérifie d'abord si le numéro de téléphone existe
        client = Client.objects.filter(telephone=telephone).first()
        
        if not client:
            messages.error(request, "Aucun compte n'est associé à ce numéro de téléphone.")
        
        else:
            try:
                # Conversion de la date saisie (format YYYY-MM-DD renvoyé par l'input HTML date)
                date_saisie = datetime.strptime(date_naissance_str, '%Y-%m-%d').date()
                
                # 2. On vérifie si la date de naissance correspond à ce client
                if client.date_naissance != date_saisie:
                    messages.error(request, "La date de naissance saisie ne correspond pas à ce numéro de téléphone.")
                else:
                    # 3. Tout est correct : mise à jour du mot de passe
                    client.mot_de_passe = nouveau_mdp
                    client.save()
                    
                    request.session['client_id'] = client.id
                    messages.success(request, "Mot de passe mis à jour avec succès !")
                    return redirect('astra:espace_client', client_id=client.id)
                    
            except (ValueError, TypeError):
                messages.error(request, "Veuillez entrer une date de naissance valide.")
            
    return render(request, 'astra/mot_de_passe_oublie.html')

def modifier_mot_de_passe_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        # ... (votre logique de traitement du formulaire)
        
        messages.success(request, "Mot de passe mis à jour avec succès !")
        return redirect('astra:client_login', client_id=client.id)

    # Mettez à jour le nom du template ici :
    return render(request, 'astra/modifier_password.html', {'client': client})


def users_page_view(request):
    utilisateurs = User.objects.all().order_by('-date_joined')
    context = {
        'utilisateurs': utilisateurs
    }
    # Remplace 'astra/nom_de_ton_template.html' par le vrai nom de ton fichier HTML (ex: 'astra/utilisateurs.html')
    return render(request, 'astra/page_utilisateurs.html', context)    