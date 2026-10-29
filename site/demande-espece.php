<?php
// Recoit de l'application le nom d'une espece absente de la base (POST :
// nom, zone, version) et l'enregistre (voir demandes.php). Repond en texte
// court : l'application n'affiche rien, elle reessaie plus tard en cas
// d'echec reseau.

declare(strict_types=1);

require __DIR__ . '/demandes.php';

header('Content-Type: text/plain; charset=utf-8');
header('X-Robots-Tag: noindex, nofollow');

if ($_SERVER['REQUEST_METHOD'] !== 'POST'
    || !str_starts_with((string) ($_SERVER['HTTP_USER_AGENT'] ?? ''), 'AquaBioScope/')) {
    http_response_code(404);
    exit('Page introuvable.');
}

$name = trim((string) ($_POST['nom'] ?? ''));
$zone = (string) ($_POST['zone'] ?? '');
$version = substr(preg_replace('/[^0-9.]/', '', (string) ($_POST['version'] ?? '')), 0, 20);

if ($name === '' || mb_strlen($name, 'UTF-8') > REQUESTS_NAME_MAX_LEN || !mb_check_encoding($name, 'UTF-8')) {
    http_response_code(400);
    exit('nom invalide');
}
if (!in_array($zone, REQUESTS_ZONES, true)) {
    $zone = 'autre';
}

if (!requests_add($name, $zone, $version)) {
    http_response_code(503);
    exit('indisponible');
}
echo 'ok';
