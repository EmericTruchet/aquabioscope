<?php
// Compteur de telechargements : fonctions partagees par download.php (qui
// compte) et stats.php (qui affiche). Ouvert directement, ce fichier ne fait
// rien.
//
// Aucune donnee personnelle n'est conservee : ni adresse IP, ni navigateur,
// seulement un nombre de telechargements par jour et par systeme.

declare(strict_types=1);

date_default_timezone_set('Europe/Paris');

// Les telechargements proposes sur la page : cle utilisee dans le lien
// (download.php?os=...) => [nom affiche, adresse du fichier].
// Windows : exe heberge sur ce serveur (voir le commentaire dans index.html).
// macOS / Linux : derniere Release GitHub.
const DOWNLOADS = [
    'windows' => ['Windows', 'https://github.com/EmericTruchet/aquabioscope/releases/latest/download/AquaBioScope-Setup.exe'],
    'macos' => ['macOS', 'https://github.com/EmericTruchet/aquabioscope/releases/latest/download/AquaBioScope-macos.zip'],
    'linux' => ['Linux', 'https://github.com/EmericTruchet/aquabioscope/releases/latest/download/AquaBioScope-linux-x86_64.AppImage'],
];

// Le fichier de donnees porte l'extension .php et commence par cette ligne :
// si quelqu'un tape son adresse, le serveur l'execute et repond "introuvable"
// au lieu d'afficher les chiffres. Pas besoin de .htaccess.
const COUNTER_FILE = __DIR__ . '/compteur.data.php';
const COUNTER_GUARD = "<?php http_response_code(404); exit; ?>\n";
const COUNTER_DAYS_KEPT = 730;

/** @return array{total: int, platforms: array<string, int>, days: array<string, int>} */
function counter_decode(string $raw): array {
    $json = str_starts_with($raw, COUNTER_GUARD) ? substr($raw, strlen(COUNTER_GUARD)) : $raw;
    $data = json_decode($json, true);
    if (!is_array($data)) {
        $data = [];
    }
    return [
        'total' => (int) ($data['total'] ?? 0),
        'platforms' => is_array($data['platforms'] ?? null) ? $data['platforms'] : [],
        'days' => is_array($data['days'] ?? null) ? $data['days'] : [],
    ];
}

/** @return array{total: int, platforms: array<string, int>, days: array<string, int>} */
function counter_read(): array {
    $raw = is_file(COUNTER_FILE) ? file_get_contents(COUNTER_FILE) : '';
    return counter_decode($raw === false ? '' : $raw);
}

function counter_increment(string $platform): void {
    $handle = fopen(COUNTER_FILE, 'c+');
    if ($handle === false) {
        return; // dossier non inscriptible : on ne compte pas, mais on ne bloque pas le telechargement
    }
    // Verrou exclusif : deux telechargements simultanes ne s'ecrasent pas.
    if (flock($handle, LOCK_EX)) {
        $data = counter_decode((string) stream_get_contents($handle));
        $today = date('Y-m-d');
        $data['total']++;
        $data['platforms'][$platform] = (int) ($data['platforms'][$platform] ?? 0) + 1;
        $data['days'][$today] = (int) ($data['days'][$today] ?? 0) + 1;
        ksort($data['days']);
        $data['days'] = array_slice($data['days'], -COUNTER_DAYS_KEPT, null, true);

        ftruncate($handle, 0);
        rewind($handle);
        fwrite($handle, COUNTER_GUARD . json_encode($data));
        fflush($handle);
        flock($handle, LOCK_UN);
    }
    fclose($handle);
}

/** Robots d'indexation et verificateurs de liens : ils suivent le lien sans telecharger pour de vrai. */
function counter_is_robot(): bool {
    $agent = strtolower((string) ($_SERVER['HTTP_USER_AGENT'] ?? ''));
    if ($agent === '') {
        return true;
    }
    foreach (['bot', 'crawl', 'spider', 'slurp', 'preview', 'monitor', 'curl', 'wget', 'python', 'headless'] as $marker) {
        if (str_contains($agent, $marker)) {
            return true;
        }
    }
    return false;
}
