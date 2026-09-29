import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Cornere sau cartonase, cu liniile obisnuite de pariere.
///
/// Sectiunea spune deschis cat de mult stie modelul pe fiecare piata, pentru ca
/// diferentele sunt mari: cine da mai multe cornere e prevazut bine, totalul de
/// cornere pe meci deloc. Cifrele vin din backtest, nu din impresii.
class CountsCard extends StatelessWidget {
  const CountsCard({
    super.key,
    required this.market,
    required this.kind,
    required this.home,
    required this.away,
  });

  final CountsMarket market;
  final CountsKind kind;
  final String home;
  final String away;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: kind.titlu,
      subtitle: 'Așteptate: ${market.expectedHome.toStringAsFixed(1)} pentru $home, '
          '${market.expectedAway.toStringAsFixed(1)} pentru $away '
          '(${market.expectedTotal.toStringAsFixed(1)} în total).',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (market.winner != null) ...[
            const _Eticheta('Cine dă mai multe',
                calitate: 'cel mai bine prevăzut', bun: true),
            const SizedBox(height: 8),
            ProbabilityBar(
              home: market.winner!['home'] ?? 0,
              draw: market.winner!['draw'] ?? 0,
              away: market.winner!['away'] ?? 0,
            ),
            const SizedBox(height: 6),
            _Legenda(home: home, away: away, valori: market.winner!),
            const Divider(height: 26, color: AppColors.border),
          ],
          _Eticheta('Total pe meci', calitate: kind.calitateTotal,
              bun: kind.totalInformativ),
          const SizedBox(height: 8),
          for (final l in market.total) _LinieTotal(linie: l),
          const Divider(height: 26, color: AppColors.border),
          _Eticheta('Pe echipă', calitate: kind.calitateEchipa, bun: true),
          const SizedBox(height: 8),
          _LiniiEchipa(nume: home, linii: market.home, sufix: kind.unitate),
          const SizedBox(height: 10),
          _LiniiEchipa(nume: away, linii: market.away, sufix: kind.unitate),
          const SizedBox(height: 12),
          Text(
            '${kind.nota} Estimat din ${market.sample} de meciuri din același '
            'campionat. Pietele astea nu intră în selecțiile automate: pentru ele '
            'nu există cote istorice cu care să verificăm regula de selecție.',
            style: const TextStyle(
                fontSize: 11, color: AppColors.textSecondary, height: 1.4),
          ),
        ],
      ),
    );
  }
}

enum CountsKind {
  corners(
    titlu: 'Cornere',
    unitate: 'cornere',
    calitateTotal: 'cât media campionatului',
    calitateEchipa: 'informativ',
    totalInformativ: false,
    nota: 'Totalul pe meci nu s-a dovedit mai bun decât media campionatului în '
        'backtest, deci ia-l ca reper, nu ca predicție. Pe echipă și "cine dă '
        'mai multe" modelul chiar știe ceva.',
  ),
  cards(
    titlu: 'Cartonașe',
    unitate: 'cartonașe',
    calitateTotal: 'slab informativ',
    calitateEchipa: 'slab informativ',
    totalInformativ: true,
    nota: 'Cartonașele depind mult de arbitru, iar arbitrul nu intră în model. '
        'Modelul bate media campionatului, dar cu puțin. Galbenele și roșiile '
        'se numără la un loc.',
  );

  const CountsKind({
    required this.titlu,
    required this.unitate,
    required this.calitateTotal,
    required this.calitateEchipa,
    required this.totalInformativ,
    required this.nota,
  });

  final String titlu;
  final String unitate;
  final String calitateTotal;
  final String calitateEchipa;
  final bool totalInformativ;
  final String nota;
}

class _Eticheta extends StatelessWidget {
  const _Eticheta(this.text, {required this.calitate, required this.bun});

  final String text;
  final String calitate;
  final bool bun;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(text,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
          decoration: BoxDecoration(
            color: (bun ? AppColors.positive : AppColors.textSecondary)
                .withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(5),
          ),
          child: Text(calitate,
              style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: bun ? AppColors.positive : AppColors.textSecondary)),
        ),
      ],
    );
  }
}

class _LinieTotal extends StatelessWidget {
  const _LinieTotal({required this.linie});

  final CountLine linie;

  @override
  Widget build(BuildContext context) {
    final sub = linie.under ?? (1 - linie.over);
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        children: [
          SizedBox(
            width: 52,
            child: Text(linie.line.toStringAsFixed(1),
                style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary)),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: linie.over,
                minHeight: 7,
                backgroundColor: AppColors.surfaceHigh,
                valueColor: const AlwaysStoppedAnimation(AppColors.accentSoft),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 108,
            child: Text(
              'peste ${(linie.over * 100).toStringAsFixed(0)}% · '
              'sub ${(sub * 100).toStringAsFixed(0)}%',
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }
}

class _LiniiEchipa extends StatelessWidget {
  const _LiniiEchipa({required this.nume, required this.linii, required this.sufix});

  final String nume;
  final List<CountLine> linii;
  final String sufix;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(nume,
            style: const TextStyle(fontSize: 12.5, color: AppColors.textPrimary)),
        const SizedBox(height: 5),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            for (final l in linii)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.surfaceHigh,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.border),
                ),
                child: Text(
                  'peste ${l.line.toStringAsFixed(1)}  '
                  '${(l.over * 100).toStringAsFixed(0)}%',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.textPrimary),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _Legenda extends StatelessWidget {
  const _Legenda({required this.home, required this.away, required this.valori});

  final String home;
  final String away;
  final Map<String, double> valori;

  @override
  Widget build(BuildContext context) {
    String procent(String cheie) =>
        '${((valori[cheie] ?? 0) * 100).toStringAsFixed(0)}%';

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Flexible(
          child: Text('$home ${procent('home')}',
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11.5, color: AppColors.homeWin)),
        ),
        Text('egal ${procent('draw')}',
            style: const TextStyle(fontSize: 11.5, color: AppColors.draw)),
        Flexible(
          child: Text('$away ${procent('away')}',
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 11.5, color: AppColors.awayWin)),
        ),
      ],
    );
  }
}
