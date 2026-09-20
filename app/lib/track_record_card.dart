import 'package:flutter/material.dart';

import 'history_screen.dart';
import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Bilantul propriilor selectii, dupa ce meciurile s-au jucat.
///
/// Spre deosebire de ratele din backtest, care descriu trecutul, cifrele de
/// aici descriu exact selectiile pe care le-ai vazut in aplicatie. Daca modelul
/// incepe sa se abata de la ce a promis, se vede intai aici.
class TrackRecordCard extends StatelessWidget {
  const TrackRecordCard({super.key, required this.record});

  final TrackRecord record;

  @override
  Widget build(BuildContext context) {
    if (!record.hasResults) return _Asteptare(record: record);

    final rata = record.hitRate!;
    final profit = record.profitUnits ?? 0;

    return SectionCard(
      title: 'Bilanțul selecțiilor',
      subtitle: 'Ce s-a întâmplat cu selecțiile pe care ți le-a arătat aplicația.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('${(rata * 100).toStringAsFixed(0)}%',
                  style: const TextStyle(
                      fontSize: 30, fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary, height: 1)),
              const SizedBox(width: 10),
              Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text('${record.hits} din ${record.resolved} reușite',
                    style: const TextStyle(
                        fontSize: 13, color: AppColors.textSecondary)),
              ),
              const Spacer(),
              _Profit(units: profit, n: record.resolved),
            ],
          ),
          if (record.pending > 0) ...[
            const SizedBox(height: 6),
            Text('${record.pending} încă nejucate',
                style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
          ],
          if (record.bands.isNotEmpty) ...[
            const Divider(height: 24, color: AppColors.border),
            const Text('Pe benzi: realizat față de ce promitea backtestul',
                style: TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
            const SizedBox(height: 9),
            for (final b in record.bands) _BandRow(band: b),
          ],
          const SizedBox(height: 10),
          Text(
            record.resolved < 30
                ? 'Sub 30 de rezultate, diferențele față de backtest sunt mai '
                    'degrabă noroc decât semnal. Cifrele devin serioase pe măsură '
                    'ce se adună.'
                : 'Dacă o bandă rămâne mult sub ce promitea backtestul pe zeci de '
                    'selecții, modelul s-a abătut și merită reantrenat.',
            style: const TextStyle(
                fontSize: 11, color: AppColors.textSecondary, height: 1.35),
          ),
          _VeziToate(record: record),
        ],
      ),
    );
  }
}

/// Intrarea catre lista selectiilor, linie cu linie.
///
/// Fara ea, cifrele de mai sus ar trebui crezute pe cuvant: meciurile alese
/// ies din fereastra de trei zile a ecranului principal si nu se mai vad.
class _VeziToate extends StatelessWidget {
  const _VeziToate({required this.record});

  final TrackRecord record;

  @override
  Widget build(BuildContext context) {
    if (record.selections.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => HistoryScreen(record: record)),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 9),
            child: Row(
              children: [
                Text('Vezi toate selecțiile (${record.selections.length})',
                    style: const TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: AppColors.accentSoft)),
                const SizedBox(width: 4),
                const Icon(Icons.chevron_right,
                    size: 18, color: AppColors.accentSoft),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Profit extends StatelessWidget {
  const _Profit({required this.units, required this.n});

  final double units;
  final int n;

  @override
  Widget build(BuildContext context) {
    final culoare = units > 0 ? AppColors.positive : AppColors.negative;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text('${units >= 0 ? '+' : ''}${units.toStringAsFixed(2)}u',
            style: TextStyle(
                fontSize: 16, fontWeight: FontWeight.w700, color: culoare)),
        const SizedBox(height: 2),
        const Text('la miză fixă de 1u',
            style: TextStyle(fontSize: 10, color: AppColors.textSecondary)),
      ],
    );
  }
}

class _BandRow extends StatelessWidget {
  const _BandRow({required this.band});

  final BandRecord band;

  @override
  Widget build(BuildContext context) {
    final diferenta = band.rate - band.expected;
    // Sub zece rezultate, diferenta nu inseamna nimic: o aratam neutru.
    final semnificativ = band.count >= 10;
    final culoare = !semnificativ
        ? AppColors.textSecondary
        : (diferenta >= -0.05 ? AppColors.positive : AppColors.negative);

    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            child: Text(band.band,
                style: const TextStyle(fontSize: 12, color: AppColors.textPrimary)),
          ),
          Text('${band.hits}/${band.count}',
              style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          const Spacer(),
          Text('${(band.rate * 100).toStringAsFixed(0)}%',
              style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700, color: culoare)),
          const SizedBox(width: 6),
          Text('(promis ${(band.expected * 100).toStringAsFixed(0)}%)',
              style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

class _Asteptare extends StatelessWidget {
  const _Asteptare({required this.record});

  final TrackRecord record;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Bilanțul selecțiilor',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.hourglass_empty,
                  size: 18, color: AppColors.textSecondary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  record.total == 0
                      ? 'Încă nu s-a notat nicio selecție. Bilanțul apare după prima '
                          'rundă de meciuri.'
                      : '${record.total} selecții notate, niciun meci încheiat încă. '
                          'Rezultatele se completează singure după ce se joacă.',
                  style: const TextStyle(
                      fontSize: 12.5, color: AppColors.textSecondary, height: 1.4),
                ),
              ),
            ],
          ),
          _VeziToate(record: record),
        ],
      ),
    );
  }
}
