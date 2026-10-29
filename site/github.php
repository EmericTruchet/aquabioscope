<?php
// Telechargements comptes par GitHub sur les Releases (installations ET
// mises a jour automatiques, qui telechargent les memes fichiers), pour
// stats.php. Ouvert directement, ce fichier ne fait rien.
//
// L'API GitHub sans compte est limitee a 60 requetes par heure : le resultat
// est garde en cache une heure (github.cache.php, protege comme les autres
// fichiers de donnees).

declare(strict_types=1);

const GITHUB_RELEASES_API = 'https://api.github.com/repos/EmericTruchet/aquabioscope/releases?per_page=100';
const GITHUB_CACHE_FILE = __DIR__ . '/github.cache.php';
const GITHUB_CACHE_GUARD = "<?php http_response_code(404); exit; ?>\n";
const GITHUB_CACHE_SECONDS = 3600;
const GITHUB_MODEL_TAG = 'modele-ia'; // module IA : compte a part, ce n'est pas l'application

function github_fetch(): ?array {
    $headers = ['User-Agent: AquaBioScope-stats', 'Accept: application/vnd.github+json'];
    if (function_exists('curl_init')) {
        $ch = curl_init(GITHUB_RELEASES_API);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 8, CURLOPT_HTTPHEADER => $headers]);
        $body = curl_exec($ch);
        $ok = curl_getinfo($ch, CURLINFO_HTTP_CODE) === 200;
        curl_close($ch);
    } else {
        $context = stream_context_create(['http' => ['header' => implode("\r\n", $headers), 'timeout' => 8]]);
        $body = @file_get_contents(GITHUB_RELEASES_API, false, $context);
        $ok = $body !== false;
    }
    $data = $ok && is_string($body) ? json_decode($body, true) : null;
    return is_array($data) ? $data : null;
}

/**
 * @return array{fetched: int, versions: array<string, array{date: string, files: array<string, int>}>}|null
 *   versions de la plus ancienne a la plus recente ; null si GitHub est injoignable et sans cache.
 */
function github_downloads(): ?array {
    $raw = is_file(GITHUB_CACHE_FILE) ? (string) file_get_contents(GITHUB_CACHE_FILE) : '';
    $cached = json_decode(str_starts_with($raw, GITHUB_CACHE_GUARD) ? substr($raw, strlen(GITHUB_CACHE_GUARD)) : '', true);
    if (is_array($cached) && time() - (int) ($cached['fetched'] ?? 0) < GITHUB_CACHE_SECONDS) {
        return $cached;
    }
    $releases = github_fetch();
    if ($releases === null) {
        return is_array($cached) ? $cached : null; // chiffres de la derniere visite plutot que rien
    }
    $versions = [];
    foreach ($releases as $release) {
        $files = [];
        foreach ($release['assets'] ?? [] as $asset) {
            $files[(string) $asset['name']] = (int) $asset['download_count'];
        }
        $versions[(string) $release['tag_name']] = ['date' => substr((string) $release['created_at'], 0, 10), 'files' => $files];
    }
    uasort($versions, static fn(array $a, array $b): int => strcmp($a['date'], $b['date']));
    $result = ['fetched' => time(), 'versions' => $versions];
    @file_put_contents(GITHUB_CACHE_FILE, GITHUB_CACHE_GUARD . json_encode($result), LOCK_EX);
    return $result;
}

/** Systeme d'un fichier de Release, d'apres son nom. */
function github_platform(string $file): string {
    $name = strtolower($file);
    return match (true) {
        str_contains($name, 'linux') || str_ends_with($name, '.appimage') => 'Linux',
        str_contains($name, 'macos') => 'macOS',
        default => 'Windows',
    };
}
