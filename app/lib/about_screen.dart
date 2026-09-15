import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Ecranul care spune, fara ocolisuri, ce poate si ce nu poate modelul.
/// Cifrele vin direct din backtest, nu sunt scrise de mana.
class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key, required this.bundle});

  final PredictionBundle bundle;

  @override
  Widget build(BuildContext context) {
    final b = bundle.backtest;
    return Scaffold(
      appBar: AppBar(title: const Text('Despre model')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        children: [
          SectionCard(
            title: 'Verdictul pe scurt',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Point(
                  icon: Icons.check_circle_outline,
                  color: AppColors.positive,
                  title: 'Probabilitatile sunt corecte ca probabilitati',
                  body: 'Eroarea medie de calibrare este ${b.ece.toStringAsFixed(4)}. '
                      'Cand modelul spune 30%, evenimentul se intampla in aproximativ 30% '
                      'din cazuri. Asta a fost verificat pe ${_n(b.matchesTested)} de meciuri.',
                ),
                const SizedBox(height: 16),
                _Point(
                  icon: Icons.cancel_outlined,
                  color: AppColors.negative,
                  title: 'Modelul NU bate casele de pariuri',
                  body: 'Pe aceleasi meciuri, cotele de inchidere au fost mai precise '
                      '(${b.marketLogLoss.toStringAsFixed(5)} fata de ${b.logLoss.toStringAsFixed(5)} '
                      'la log-loss, unde mai mic inseamna mai bun). Pariurile alese dupa model '
                      'au dat randament negativ la orice prag testat.',
                ),
                const SizedBox(height: 16),
                const _Point(
                  icon: Icons.lightbulb_outline,
                  color: AppColors.accent,
                  title: 'La ce foloseste, totusi',
                  body: 'Ca punct de plecare: iti arata cat de dezechilibrat e un meci, '
                      'cate goluri se asteapta, cum arata forma si istoricul direct — '
                      'toate calculate din date, nu din impresii.',
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SectionCard(
            title: 'Cifrele backtest-ului',
            subtitle: 'Perioada ${b.period}, validare walk-forward, fara scurgeri de date.',
            child: Column(
              children: [
                _Stat('Meciuri testate', _n(b.matchesTested)),
                _Stat('Acuratete 1X2', '${(b.accuracy * 100).toStringAsFixed(1)}%'),
                _Stat('Log-loss model', b.logLoss.toStringAsFixed(5)),
                _Stat('Log-loss piata', b.marketLogLoss.toStringAsFixed(5)),
                _Stat('Eroare de calibrare', b.ece.toStringAsFixed(4)),
                _Stat('Bate piata', b.beatsMarket ? 'Da' : 'Nu'),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SectionCard(
            title: 'Cum functioneaza',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Modelul este Dixon-Coles: fiecare echipa are o forta de atac si una de '
                  'aparare, estimate din meciurile anterioare. Numarul de goluri urmeaza o '
                  'distributie Poisson, cu o corectie pentru scorurile mici, unde Poisson '
                  'simplu subestimeaza egalurile.\n\n'
                  'Peste asta, un al doilea model estimeaza aceleasi forte din suturile pe '
                  'poarta. Suturile sunt de aproximativ zece ori mai numeroase decat golurile, '
                  'deci masoara mai stabil cat de bine joaca o echipa. Cele doua estimari se '
                  'combina in parti egale.\n\n'
                  'Meciurile vechi conteaza mai putin decat cele recente, cu o injumatatire '
                  'a importantei la aproximativ 230 de zile.',
                  style: TextStyle(fontSize: 13, height: 1.5),
                ),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceHigh,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    'Model: ${bundle.modelName}\n'
                    'Date: football-data.co.uk (gratuite)\n'
                    'Generat: ${DateFormat('d MMMM yyyy, HH:mm', 'ro').format(bundle.generatedAt)}',
                    style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary, height: 1.5),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static String _n(int value) =>
      value.toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]}.');
}

class _Point extends StatelessWidget {
  const _Point({
    required this.icon,
    required this.color,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color, size: 19),
        const SizedBox(width: 11),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Text(body,
                  style: const TextStyle(
                      fontSize: 12.5, height: 1.45, color: AppColors.textSecondary)),
            ],
          ),
        ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
          Text(value, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
