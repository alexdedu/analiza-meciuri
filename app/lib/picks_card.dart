import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Selecțiile modelului, grupate pe meci.
///
/// Un meci are de obicei mai multe piețe care trec filtrele — rezultatul,
/// golurile, cornerele, cartonașele. Alegerea dintre ele e a utilizatorului,
/// nu a unei ordonări dintr-un fișier, așa că apar toate, cu cifrele lângă
/// fiecare: cât de probabil, la ce cotă, și cât a ieșit istoric.
class PicksCard extends StatelessWidget {
  const PicksCard({
    super.key,
    required this.matches,
    required this.countsRecord,
    required this.onTap,
  });

  final List<RecommendedMatch> matches;
  final CountsRecord? countsRecord;
  final void Function(String matchId) onTap;

  @override
  Widget build(BuildContext context) {
    if (matches.isEmpty) return const _EmptyCard();

    return SectionCard(
      title: 'Selecțiile modelului',
      subtitle: 'Fiecare meci cu piețele care trec filtrele. Alegi tu care '
          'merită la cota pe care o găsești.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final m in matches)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _MatchBlock(match: m, onTap: () => onTap(m.matchId)),
            ),
          const Divider(height: 8, color: AppColors.border),
          const SizedBox(height: 10),
          const Text(
            'La rezultat și goluri există cote adevărate, deci selecția trece '
            'și prin filtrul de acord cu piața: măsurat, 64,3% reușite, dar '
            'randamentul iese pozitiv doar la cea mai bună cotă de pe piață.\n\n'
            'La cornere și cartonașe nu există cote nicăieri, deci apare cota '
            'corectă — reperul tău: dacă găsești mai mult, pariul are sens. '
            'Procentele de acolo s-au adeverit la mai puțin de două puncte '
            'distanță, pe 16.676 de meciuri.',
            style: TextStyle(fontSize: 11, color: AppColors.textSecondary, height: 1.35),
          ),
          if (countsRecord != null && countsRecord!.resolved > 0) ...[
            const SizedBox(height: 10),
            Text(
              'Cornere și cartonașe până acum: ${countsRecord!.hits} din '
              '${countsRecord!.resolved}'
              '${countsRecord!.hitRate == null ? '' : ' '
                  '(${(countsRecord!.hitRate! * 100).toStringAsFixed(0)}%, '
                  'promis ${(countsRecord!.expected * 100).toStringAsFixed(0)}%)'}',
              style: const TextStyle(
                  fontSize: 11.5, fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary),
            ),
          ],
        ],
      ),
    );
  }
}

class _MatchBlock extends StatelessWidget {
  const _MatchBlock({required this.match, required this.onTap});

  final RecommendedMatch match;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surfaceHigh,
      borderRadius: BorderRadius.circular(11),
      child: InkWell(
        borderRadius: BorderRadius.circular(11),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 11),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text('${match.home} – ${match.away}',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary)),
                  ),
                  const SizedBox(width: 8),
                  Text(match.time,
                      style: const TextStyle(
                          fontSize: 11, color: AppColors.textSecondary)),
                ],
              ),
              const SizedBox(height: 2),
              Text(match.leagueName,
                  style: const TextStyle(
                      fontSize: 10.5, color: AppColors.textSecondary)),
              const SizedBox(height: 9),
              for (final p in match.picks)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: _PickRow(pick: p),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PickRow extends StatelessWidget {
  const _PickRow({required this.pick});

  final MatchPick pick;

  @override
  Widget build(BuildContext context) {
    final culoare = pick.hasOdds ? AppColors.accentSoft : AppColors.highlight;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _FamilyTag(family: pick.family, color: culoare),
        const SizedBox(width: 9),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(pick.marketLabel,
                  style: const TextStyle(
                      fontSize: 12.5, color: AppColors.textPrimary)),
              const SizedBox(height: 2),
              Text(
                pick.hasOdds
                    ? 'cotă ${pick.odds!.toStringAsFixed(2)}  ·  istoric '
                        '${(pick.historicalHitRate * 100).toStringAsFixed(0)}%'
                    : 'cotă corectă ${pick.fairOdds.toStringAsFixed(2)}  ·  istoric '
                        '${(pick.historicalHitRate * 100).toStringAsFixed(0)}%',
                style: const TextStyle(fontSize: 10.5, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Text('${(pick.probability * 100).toStringAsFixed(0)}%',
            style: TextStyle(
                fontSize: 14, fontWeight: FontWeight.w700, color: culoare)),
      ],
    );
  }
}

class _FamilyTag extends StatelessWidget {
  const _FamilyTag({required this.family, required this.color});

  final String family;
  final Color color;

  static const _scurt = {
    '1x2': 'REZ',
    'goluri': 'GOL',
    'cornere': 'CRN',
    'cartonașe': 'CRT',
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 38,
      padding: const EdgeInsets.symmetric(vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(_scurt[family] ?? family.toUpperCase(),
          textAlign: TextAlign.center,
          style: TextStyle(
              fontSize: 9.5, fontWeight: FontWeight.w800, color: color)),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      title: 'Selecțiile modelului',
      child: Text(
        'Niciun meci nu trece filtrele acum. Se cere o cotă de cel puțin 1.45, '
        'date solide despre ambele echipe, și ca modelul să nu se creadă mai '
        'deștept decât piața.',
        style: TextStyle(fontSize: 12.5, color: AppColors.textSecondary, height: 1.4),
      ),
    );
  }
}
