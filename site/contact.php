<?php
// Traitement du formulaire de contact de la page AquaBioScope.
// Envoie le message par mail() (disponible sans configuration particuliere
// sur la plupart des hebergements PHP). Si la reception s'avere peu fiable
// (mail() peut finir en spam selon la reputation du serveur), on pourra
// passer a un envoi SMTP authentifie (PHPMailer) en remplacement.

declare(strict_types=1);

const DEST_EMAIL = 'contact@hoxo.fr';
const REDIRECT_BASE = 'index.html';

function redirect(string $status): never {
    header('Location: ' . REDIRECT_BASE . '?contact=' . $status . '#contact');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    redirect('error');
}

// Piege a bots : champ cache, doit rester vide pour un envoi humain.
if (!empty($_POST['site_web'] ?? '')) {
    redirect('ok'); // on fait croire que ca a marche, sans rien envoyer
}

$name = trim((string) ($_POST['name'] ?? ''));
$email = trim((string) ($_POST['email'] ?? ''));
$message = trim((string) ($_POST['message'] ?? ''));

if ($message === '' || $email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    redirect('error');
}

// Les champs utilisateur ne doivent jamais contenir de saut de ligne dans
// les en-tetes (injection d'en-tetes mail).
$sanitize = static fn(string $s): string => str_replace(["\r", "\n"], ' ', $s);
$name = $sanitize($name) ?: 'Anonyme';
$emailHeader = $sanitize($email);

$subject = 'Contact AquaBioScope de ' . $name;
$body = "Nom : $name\nEmail : $email\n\nMessage :\n$message\n";
$headers = "From: AquaBioScope <no-reply@hoxo.fr>\r\n"
    . "Reply-To: $emailHeader\r\n"
    . "Content-Type: text/plain; charset=UTF-8";

$sent = mail(DEST_EMAIL, $subject, $body, $headers);

redirect($sent ? 'ok' : 'error');
