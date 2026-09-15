import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'models.dart';
import 'repository.dart';
import 'theme.dart';
import 'value_calculator.dart';
import 'widgets.dart';

class DetailScreen extends StatelessWidget {
  const DetailScreen({super.key, required this.match, required this.store});

  final MatchPrediction match;
  final OddsStore store;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(match.leagueName)),
      body: ListView(
        // Ultimul card ar intra sub bara de navigare fara marginea telefonului.
        padding: EdgeInsets.fromLTRB(16, 4, 16, 32 + MediaQuery.paddingOf(context).bottom),
        children: [
          _Header(match: match),
          const SizedBox(height: 14),
          _OutcomeCard(match: match),
          const SizedBox(height: 12),
          _GoalsCard(match: match),
          const SizedBox(height: 12),
          ValueCalculator(match: match, store: store),
          const SizedBox(height: 12),
          _FormCard(match: match),
          if (match.headToHead.isNotEmpty) ...[
            const SizedBox(height: 12),
            _HeadToHeadCard(match: match),
          ],
          const SizedBox(height: 12),
          _ExplanationCard(match: match),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    final when = DateFormat("EEEE, d MMMM", 'ro').format(match.date);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${match.home}  –  ${match.away}',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, height: 1.25)),
        const SizedBox(height: 6),
        Row(
          children: [
            Text('${when[0].toUpperCase()}${when.substring(1)}'
                '${match.time.isNotEmpty ? ', ${match.time}' : ''}',
                style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
            const SizedBox(width: 10),
            ConfidenceBadge(confidence: match.confidence),
          ],
        ),
        if (match.confidence != Confidence.ridicata) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(11),
            decoration: BoxDecoration(
              color: AppColors.warning.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              'Estimarile se bazeaza pe ${match.homeMatches} meciuri pentru ${match.home} '
              'si ${match.awayMatches} pentru ${match.away} in liga curenta. Sub 15 meciuri, '
              'forta echipei e estimata slab — trateaza probabilitatile cu rezerva.',
              style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary, height: 1.35),
            ),
          ),
        ],
      ],
    );
  }
}

class _OutcomeCard extends StatelessWidget {
  const _OutcomeCard({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Rezultat final',
      subtitle: match.referenceOdds.isEmpty
          ? null
          : 'In paranteza, cota de referinta din feed (Bet365, orientativa).',
      child: Column(
        children: [
          ProbabilityRow(
            label: match.home,
            probability: match.p('p_home'),
            color: AppColors.homeWin,
            trailing: _odds(match.referenceOdds['home']),
          ),
          ProbabilityRow(
            label: 'Egal',
            probability: match.p('p_draw'),
            color: AppColors.draw,
            trailing: _odds(match.referenceOdds['draw']),
          ),
          ProbabilityRow(
            label: match.away,
            probability: match.p('p_away'),
            color: AppColors.awayWin,
            trailing: _odds(match.referenceOdds['away']),
          ),
        ],
      ),
    );
  }

  static Widget? _odds(double? value) {
    if (value == null) return null;
    return SizedBox(
      width: 52,
      child: Text('(${value.toStringAsFixed(2)})',
          textAlign: TextAlign.right,
          style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
    );
  }
}

class _GoalsCard extends StatelessWidget {
  const _GoalsCard({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Goluri',
      subtitle: 'Goluri asteptate: ${match.expectedGoalsHome.toStringAsFixed(2)} pentru '
          '${match.home}, ${match.expectedGoalsAway.toStringAsFixed(2)} pentru ${match.away}.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ProbabilityRow(
              label: 'Peste 2.5', probability: match.p('p_over25'), color: AppColors.accent),
          ProbabilityRow(
              label: 'Sub 2.5', probability: match.p('p_under25'), color: AppColors.accent),
          ProbabilityRow(
              label: 'Ambele inscriu', probability: match.p('p_btts'), color: AppColors.accent),
          const SizedBox(height: 14),
          const Text('Cele mai probabile scoruri',
              style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: match.topScores
                .map((s) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceHigh,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '${s.score}   ${(s.probability * 100).toStringAsFixed(1)}%',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }
}

class _FormCard extends StatelessWidget {
  const _FormCard({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Forma recenta',
      subtitle: 'Cel mai recent meci este ultimul din dreapta.',
      child: Column(
        children: [
          _TeamRow(name: match.home, context: match.homeContext),
          const Divider(height: 26, color: AppColors.border),
          _TeamRow(name: match.away, context: match.awayContext),
        ],
      ),
    );
  }
}

class _TeamRow extends StatelessWidget {
  const _TeamRow({required this.name, required this.context});

  final String name;
  final TeamContext context;

  @override
  Widget build(BuildContext ctx) {
    final stats = <String>[
      if (context.goalsForAvg != null) 'marcate ${context.goalsForAvg!.toStringAsFixed(2)}/meci',
      if (context.goalsAgainstAvg != null)
        'primite ${context.goalsAgainstAvg!.toStringAsFixed(2)}/meci',
      if (context.shotsOnTargetAvg != null)
        'suturi pe poarta ${context.shotsOnTargetAvg!.toStringAsFixed(1)}',
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(name,
                  style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
                  overflow: TextOverflow.ellipsis),
            ),
            FormStrip(form: context.form),
          ],
        ),
        if (stats.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(stats.join('  ·  '),
              style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
        ],
      ],
    );
  }
}

class _HeadToHeadCard extends StatelessWidget {
  const _HeadToHeadCard({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Intalniri directe',
      child: Column(
        children: match.headToHead
            .map((h) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 78,
                        child: Text(h.date,
                            style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
                      ),
                      Expanded(
                        child: Text('${h.home} – ${h.away}',
                            style: const TextStyle(fontSize: 12.5),
                            overflow: TextOverflow.ellipsis),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceHigh,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(h.score,
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                      ),
                    ],
                  ),
                ))
            .toList(),
      ),
    );
  }
}

class _ExplanationCard extends StatelessWidget {
  const _ExplanationCard({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Ce vede modelul',
      child: Text(match.explanation,
          style: const TextStyle(fontSize: 13, height: 1.5, color: AppColors.textPrimary)),
    );
  }
}
