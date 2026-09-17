import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Sectiunea cu pariurile alese automat de model.
///
/// Fiecare linie arata si cat de des s-au confirmat istoric selectiile din
/// aceeasi banda de probabilitate, ca sa se vada la ce sa te astepti.
class RecommendationsCard extends StatelessWidget {
  const RecommendationsCard({
    super.key,
    required this.recommendations,
    required this.onTap,
  });

  final List<Recommendation> recommendations;
  final void Function(String matchId) onTap;

  @override
  Widget build(BuildContext context) {
    if (recommendations.isEmpty) return const _EmptyCard();

    return SectionCard(
      title: 'Selecțiile modelului',
      subtitle: 'Meciurile cele mai previzibile din perioada afișată, '
          'alese acolo unde modelul e sigur și cotele îi dau dreptate.',
      child: Column(
        children: [
          for (final r in recommendations)
            Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: _Row(rec: r, onTap: () => onTap(r.matchId)),
            ),
          const SizedBox(height: 4),
          const Text(
            'Nu sunt pariuri sigure. Selecția după avantajul față de cotă — metoda '
            'intuitivă — a dat 31,5% reușite și randament negativ în backtest, '
            'așa că modelul nu o folosește.',
            style: TextStyle(fontSize: 11, color: AppColors.textSecondary, height: 1.35),
          ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.rec, required this.onTap});

  final Recommendation rec;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    // Verde doar peste 70%: acolo rata istorica masurata trece de 75%.
    final culoare = rec.probability >= 0.70 ? AppColors.positive : AppColors.accentSoft;

    return Material(
      color: AppColors.surfaceHigh,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text('${rec.home} – ${rec.away}',
                        style: const TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w600),
                        overflow: TextOverflow.ellipsis),
                  ),
                  Text('${rec.date.substring(8)}.${rec.date.substring(5, 7)}'
                      '${rec.time.isNotEmpty ? '  ${rec.time}' : ''}',
                      style: const TextStyle(
                          fontSize: 11, color: AppColors.textSecondary)),
                ],
              ),
              const SizedBox(height: 7),
              Row(
                children: [
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: culoare.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(rec.marketLabel,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w600, color: culoare)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text('${(rec.probability * 100).toStringAsFixed(0)}%',
                      style: TextStyle(
                          fontSize: 15, fontWeight: FontWeight.w700, color: culoare)),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'Cotă ${rec.odds.toStringAsFixed(2)}  ·  piața dă '
                '${(rec.marketProbability * 100).toStringAsFixed(0)}%  ·  '
                'istoric la ${rec.band}: ${(rec.historicalHitRate * 100).toStringAsFixed(0)}% reușite',
                style: const TextStyle(fontSize: 10.5, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard();

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Selecțiile modelului',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.filter_alt_outlined, size: 18,
                  color: AppColors.textSecondary.withValues(alpha: 0.8)),
              const SizedBox(width: 9),
              const Expanded(
                child: Text('Niciun meci nu trece filtrele acum.',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Ca să apară aici, un meci are nevoie de trei lucruri deodată: date '
            'solide despre ambele echipe, o probabilitate de cel puțin 60% pe o '
            'piață, și o cotă care confirmă ce spune modelul. Lista rămâne goală '
            'mai des decât plină — asta e intenționat.',
            style: TextStyle(fontSize: 11.5, color: AppColors.textSecondary, height: 1.4),
          ),
        ],
      ),
    );
  }
}
