<?php
// Liens de telechargement de la page AquaBioScope (download.php?os=windows,
// macos ou linux) : compte le telechargement (voir compteur.php), puis
// redirige vers le fichier.

declare(strict_types=1);

require __DIR__ . '/compteur.php';

$platform = (string) ($_GET['os'] ?? '');
if (!isset(DOWNLOADS[$platform])) {
    // Lien inconnu : retour a la page plutot qu'une erreur. La destination
    // vient toujours de la liste DOWNLOADS, jamais de l'adresse demandee.
    header('Location: index.html', true, 302);
    exit;
}

// Seul un vrai clic compte : pas les requetes HEAD, ni les robots.
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET' && !counter_is_robot()) {
    counter_increment($platform);
}

header('Cache-Control: no-store'); // sinon le navigateur peut sauter ce script la fois suivante
header('Location: ' . DOWNLOADS[$platform][1], true, 302);
exit;
