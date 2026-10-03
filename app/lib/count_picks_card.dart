import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Selecțiile pe cornere și cartonașe.
///
/// Stau separat de celelalte dintr-un motiv care conteaza: pentru pietele astea
/// nu exista cote in nicio sursa, deci nu se poate verifica daca modelul bate
/// piata, si nici nu se poate vorbi de randament. Ce se poate verifica -- si
/// s-a verificat -- e daca procentele se adeveresc.
class CountPicksCard extends StatelessWidget {
  const CountPicksCard({
    super.key,
    required this.picks,
    required this.record,
    required this.onTap,
  });

  final List<CountPick> picks;
  final CountsRecord? record;
  final void Function(String matchId) onTap;

  @override
  Widget build(BuildContext context) {
    if (picks.isEmpty) return const SizedBox.shrink();

    return SectionCard(
      title: 'Cornere și cartonașe',
      subtitle: 'Piețele în care modelul s-a dovedit calibrat, la o cotă care '
          'merită jucată.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final p in picks)
            Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: _Row(pick: p, onTap: () => onTap(p.matchId)),
            ),
          if (record != null && record!.resolved > 0) ...[
            const Divider(height: 22, color: AppColors.border),
            _Bilant(record: record!),
          ],
          const SizedBox(height: 8),
          const Text(
            'Pentru cornere și cartonașe nu există cote nicăieri — nici în '
            'arhive, nici la casele din API. Deci nu pot spune dacă bat piața, '
            'doar că procentele se adeveresc: măsurat pe 16.676 de meciuri, în '
            'banda folosită aici realitatea a fost la mai puțin de două puncte '
            'de promisiune. Cota corectă e reperul tău: dacă găsești mai mult, '
            'pariul are sens.',
            style: TextStyle(fontSize: 11, color: AppColors.textSecondary, height: 1.35),
          ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.pick, required this.onTap});

  final CountPick pick;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surfaceHigh,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(pick.marketLabel,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppColors.accentSoft)),
                  ),
                  const SizedBox(width: 10),
                  Text('${(pick.probability * 100).toStringAsFixed(0)}%',
                      style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppColors.accentSoft)),
                ],
              ),
              const SizedBox(height: 3),
              Text('${pick.home} – ${pick.away}',
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: AppColors.textPrimary)),
              const SizedBox(height: 4),
              Text(
                'Cotă corectă ${pick.fairOdds.toStringAsFixed(2)}  ·  istoric '
                '${(pick.historicalHitRate * 100).toStringAsFixed(0)}% reușite',
                style: const TextStyle(fontSize: 10.5, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Bilant extends StatelessWidget {
  const _Bilant({required this.record});

  final CountsRecord record;

  @override
  Widget build(BuildContext context) {
    final rata = record.hitRate;
    final culoare = rata == null
        ? AppColors.textSecondary
        : (rata >= record.expected - 0.05 ? AppColors.positive : AppColors.negative);

    return Row(
      children: [
        const Text('Până acum:',
            style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
        const SizedBox(width: 8),
        Text('${record.hits} din ${record.resolved}',
            style: const TextStyle(
                fontSize: 13, fontWeight: FontWeight.w700,
                color: AppColors.textPrimary)),
        const SizedBox(width: 8),
        if (rata != null)
          Text('${(rata * 100).toStringAsFixed(0)}%',
              style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700, color: culoare)),
        const Spacer(),
        Text('promis ${(record.expected * 100).toStringAsFixed(0)}%',
            style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
      ],
    );
  }
}
