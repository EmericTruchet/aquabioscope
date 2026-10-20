<?php
// Page privee : nombre de telechargements d'AquaBioScope.
// A ouvrir avec la cle dans l'adresse : stats.php?cle=...
// Sans la bonne cle, la page repond "introuvable" comme si elle n'existait pas.

declare(strict_types=1);

require __DIR__ . '/compteur.php';

// La cle n'est pas dans le depot (public) : stats.cle.php, present seulement
// sur le serveur, la renvoie (<?php return '...';). Il est ecrit lors de la mise
// en ligne a partir du secret GitHub STATS_KEY ; pour changer la cle, changer
// ce secret puis relancer la mise en ligne du site.
$statsKey = is_file(__DIR__ . '/stats.cle.php') ? include __DIR__ . '/stats.cle.php' : '';

if (!is_string($statsKey) || $statsKey === '' || !hash_equals($statsKey, (string) ($_GET['cle'] ?? ''))) {
    http_response_code(404);
    exit('Page introuvable.');
}

header('Cache-Control: no-store');
header('X-Robots-Tag: noindex, nofollow');

$data = counter_read();
$days = $data['days'];

/** Total des $count derniers jours, aujourd'hui compris. */
$sum_last = static function (int $count) use ($days): int {
    $sum = 0;
    for ($i = 0; $i < $count; $i++) {
        $sum += (int) ($days[date('Y-m-d', strtotime("-$i days"))] ?? 0);
    }
    return $sum;
};

$last30 = [];
for ($i = 0; $i < 30; $i++) {
    $day = date('Y-m-d', strtotime("-$i days"));
    $last30[$day] = (int) ($days[$day] ?? 0);
}
$peak = max(1, max($last30));
$first_day = array_key_first($days);
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>AquaBioScope — téléchargements</title>
<style>
  body { margin: 0; padding: 40px 20px; background: #F7F2E7; color: #14262E;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }
  main { max-width: 640px; margin: 0 auto; }
  h1 { font-size: 1.4rem; color: #0C232B; margin: 0 0 4px; }
  h2 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: #5C6A66; margin: 0 0 10px; }
  p.sub { color: #5C6A66; margin: 0 0 28px; font-size: 0.92rem; }
  .cards { display: grid; gap: 12px; margin-bottom: 28px; }
  .cards.four { grid-template-columns: repeat(4, 1fr); }
  .cards.three { grid-template-columns: repeat(3, 1fr); }
  .card { background: white; border: 1px solid #E7DFCC; border-radius: 12px; padding: 16px 12px; text-align: center; }
  .card.main { background: #0E7C86; border-color: #0E7C86; color: white; }
  .num { display: block; font-size: 1.9rem; font-weight: 700; }
  .label { display: block; font-size: 0.8rem; opacity: 0.8; }
  table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #E7DFCC; border-radius: 12px; overflow: hidden; }
  td { padding: 7px 14px; border-bottom: 1px solid #F3EEE0; font-size: 0.9rem; }
  tr:last-child td { border-bottom: none; }
  td.day { width: 120px; color: #5C6A66; white-space: nowrap; }
  td.count { width: 40px; text-align: right; font-weight: 600; }
  .bar { height: 10px; border-radius: 5px; background: #1298A5; min-width: 2px; }
  .bar.zero { background: #E7DFCC; }
  @media (max-width: 520px) { .cards.four { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<main>
  <h1>Téléchargements d'AquaBioScope</h1>
  <p class="sub">
    <?= $first_day ? 'Compteur démarré le ' . date('d/m/Y', strtotime($first_day)) . '.' : 'Aucun téléchargement compté pour l\'instant.' ?>
    Un clic sur un bouton du site = 1, robots exclus.
  </p>

  <div class="cards four">
    <div class="card main"><span class="num"><?= $data['total'] ?></span><span class="label">au total</span></div>
    <div class="card"><span class="num"><?= $sum_last(1) ?></span><span class="label">aujourd'hui</span></div>
    <div class="card"><span class="num"><?= $sum_last(7) ?></span><span class="label">7 derniers jours</span></div>
    <div class="card"><span class="num"><?= $sum_last(30) ?></span><span class="label">30 derniers jours</span></div>
  </div>

  <h2>Par système (depuis le début)</h2>
  <div class="cards three">
    <?php foreach (DOWNLOADS as $key => [$name]): ?>
    <div class="card"><span class="num"><?= (int) ($data['platforms'][$key] ?? 0) ?></span><span class="label"><?= htmlspecialchars($name) ?></span></div>
    <?php endforeach; ?>
  </div>

  <h2>30 derniers jours, tous systèmes</h2>
  <table>
    <?php foreach ($last30 as $day => $count): ?>
    <tr>
      <td class="day"><?= date('d/m/Y', strtotime($day)) ?></td>
      <td><div class="bar<?= $count ? '' : ' zero' ?>" style="width: <?= $count ? round(100 * $count / $peak) : 0 ?>%"></div></td>
      <td class="count"><?= $count ?></td>
    </tr>
    <?php endforeach; ?>
  </table>
</main>
</body>
</html>
