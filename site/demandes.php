<?php
// Especes demandees : noms d'especes absentes de la base, ajoutes "a la main"
// dans l'application (bouton « Ajouter comme espece non repertoriee »).
// Fonctions partagees par demande-espece.php (qui enregistre) et stats.php
// (qui affiche). Ouvert directement, ce fichier ne fait rien.
//
// Aucune donnee personnelle n'est conservee : ni adresse IP, ni identifiant,
// seulement le nom tape, la zone de plongee, la version de l'application et
// la date. Les demandes identiques sont regroupees (nombre de demandes).

declare(strict_types=1);

date_default_timezone_set('Europe/Paris');

// Meme protection que compteur.data.php : ouvert dans un navigateur, le
// fichier repond "introuvable" au lieu d'afficher les donnees.
const REQUESTS_FILE = __DIR__ . '/demandes.data.php';
const REQUESTS_GUARD = "<?php http_response_code(404); exit; ?>\n";
const REQUESTS_MAX_NAMES = 5000;   // garde-fou contre un remplissage abusif
const REQUESTS_NAME_MAX_LEN = 80;
const REQUESTS_ZONES = ['mediterranee', 'atlantique', 'mer-rouge', 'caraibes', 'indo-pacifique',
                        'ocean-indien', 'pacifique', 'autre'];

/** Cle de regroupement : minuscules, sans accents ni espaces superflus. */
function request_key(string $name): string {
    $name = mb_strtolower(trim(preg_replace('/\s+/u', ' ', $name)), 'UTF-8');
    $ascii = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $name);
    return $ascii === false ? $name : preg_replace('/[^a-z0-9 ]/', '', $ascii);
}

/** @return array<string, array{nom: string, total: int, zones: array<string, int>, premiere: string, derniere: string, version: string, traitee: ?string}> */
function requests_decode(string $raw): array {
    $json = str_starts_with($raw, REQUESTS_GUARD) ? substr($raw, strlen(REQUESTS_GUARD)) : $raw;
    $data = json_decode($json, true);
    return is_array($data) ? $data : [];
}

function requests_read(): array {
    $raw = is_file(REQUESTS_FILE) ? file_get_contents(REQUESTS_FILE) : '';
    return requests_decode($raw === false ? '' : $raw);
}

/** Applique $change aux donnees, sous verrou exclusif (deux envois simultanes ne s'ecrasent pas). */
function requests_update(callable $change): bool {
    $handle = fopen(REQUESTS_FILE, 'c+');
    if ($handle === false) {
        return false;
    }
    $ok = false;
    if (flock($handle, LOCK_EX)) {
        $data = requests_decode((string) stream_get_contents($handle));
        $data = $change($data);
        ftruncate($handle, 0);
        rewind($handle);
        fwrite($handle, REQUESTS_GUARD . json_encode($data, JSON_UNESCAPED_UNICODE));
        fflush($handle);
        flock($handle, LOCK_UN);
        $ok = true;
    }
    fclose($handle);
    return $ok;
}

function requests_add(string $name, string $zone, string $version): bool {
    $key = request_key($name);
    if ($key === '') {
        return false;
    }
    return requests_update(static function (array $data) use ($key, $name, $zone, $version): array {
        if (!isset($data[$key]) && count($data) >= REQUESTS_MAX_NAMES) {
            return $data;
        }
        $today = date('Y-m-d');
        $entry = $data[$key] ?? ['nom' => $name, 'total' => 0, 'zones' => [], 'premiere' => $today, 'traitee' => null];
        $entry['total']++;
        $entry['zones'][$zone] = (int) ($entry['zones'][$zone] ?? 0) + 1;
        $entry['derniere'] = $today;
        $entry['version'] = $version;
        $entry['traitee'] = null; // redemandee apres traitement : a revoir
        $data[$key] = $entry;
        return $data;
    });
}

function requests_mark_done(string $key, bool $done): bool {
    return requests_update(static function (array $data) use ($key, $done): array {
        if (isset($data[$key])) {
            $data[$key]['traitee'] = $done ? date('Y-m-d') : null;
        }
        return $data;
    });
}
