import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'models.dart';
import 'theme.dart';

/// Lista completa a selectiilor notate, cu rezultatul fiecareia.
///
/// Ecranul principal arata doar trei zile, deci un meci ales luni dispare de
/// acolo marti. Aici raman toate, cu scorul si cu verdictul, ca sa se poata
/// verifica bilantul linie cu linie, nu doar pe total.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key, required this.record});

  final TrackRecord record;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

enum _Filtru { toate, jucate, inAsteptare }

class _HistoryScreenState extends State<HistoryScreen> {
  _Filtru _filtru = _Filtru.toate;

  @override
  Widget build(BuildContext context) {
    final toate = widget.record.selections;
    final selectii = switch (_filtru) {
      _Filtru.toate => toate,
      _Filtru.jucate => toate.where((s) => !s.isPending).toList(),
      _Filtru.inAsteptare => toate.where((s) => s.isPending).toList(),
    };

    // Gruparea pe zi pastreaza ordinea primita: cele mai noi intai.
    final peZile = <DateTime, List<SelectionRecord>>{};
    for (final s in selectii) {
      final zi = DateTime(s.date.year, s.date.month, s.date.day);
      peZile.putIfAbsent(zi, () => []).add(s);
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Istoricul selecțiilor')),
      body: toate.isEmpty
          ? const _Gol()
          : ListView(
              padding: EdgeInsets.fromLTRB(
                  0, 4, 0, MediaQuery.paddingOf(context).bottom + 28),
              children: [
                _Sumar(record: widget.record),
                _Filtre(
                  curent: _filtru,
                  jucate: toate.where((s) => !s.isPending).length,
                  inAsteptare: toate.where((s) => s.isPending).length,
                  onChanged: (f) => setState(() => _filtru = f),
                ),
                if (selectii.isEmpty)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 28, 16, 0),
                    child: Text('Nicio selecție aici deocamdată.',
                        style: TextStyle(
                            fontSize: 13, color: AppColors.textSecondary)),
                  ),
                for (final zi in peZile.keys) ...[
                  _ZiHeader(day: zi),
                  for (final s in peZile[zi]!)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                      child: _Linie(selectie: s),
                    ),
                ],
              ],
            ),
    );
  }
}

/// Totalurile, repetate aici ca sa nu fie nevoie de drumul inapoi.
class _Sumar extends StatelessWidget {
  const _Sumar({required this.record});

  final TrackRecord record;

  @override
  Widget build(BuildContext context) {
    final rata = record.hitRate;
    final profit = record.profitUnits;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.surfaceHigh,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          _Cifra(
            valoare: rata == null ? '—' : '${(rata * 100).toStringAsFixed(0)}%',
            eticheta: 'reușite',
          ),
          const SizedBox(width: 26),
          _Cifra(
            valoare: '${record.hits}/${record.resolved}',
            eticheta: 'verificate',
          ),
          const Spacer(),
          if (profit != null)
            _Cifra(
              valoare:
                  '${profit >= 0 ? '+' : ''}${profit.toStringAsFixed(2)}u',
              eticheta: 'la miză de 1u',
              culoare: profit > 0 ? AppColors.positive : AppColors.negative,
              laDreapta: true,
            ),
        ],
      ),
    );
  }
}

class _Cifra extends StatelessWidget {
  const _Cifra({
    required this.valoare,
    required this.eticheta,
    this.culoare,
    this.laDreapta = false,
  });

  final String valoare;
  final String eticheta;
  final Color? culoare;
  final bool laDreapta;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment:
          laDreapta ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Text(valoare,
            style: TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.w800,
                color: culoare ?? AppColors.textPrimary)),
        const SizedBox(height: 2),
        Text(eticheta,
            style: const TextStyle(
                fontSize: 11, color: AppColors.textSecondary)),
      ],
    );
  }
}

class _Filtre extends StatelessWidget {
  const _Filtre({
    required this.curent,
    required this.jucate,
    required this.inAsteptare,
    required this.onChanged,
  });

  final _Filtru curent;
  final int jucate;
  final int inAsteptare;
  final void Function(_Filtru) onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        children: [
          _Chip(
            label: 'Toate (${jucate + inAsteptare})',
            selected: curent == _Filtru.toate,
            onTap: () => onChanged(_Filtru.toate),
          ),
          _Chip(
            label: 'Jucate ($jucate)',
            selected: curent == _Filtru.jucate,
            onTap: () => onChanged(_Filtru.jucate),
          ),
          _Chip(
            label: 'În așteptare ($inAsteptare)',
            selected: curent == _Filtru.inAsteptare,
            onTap: () => onChanged(_Filtru.inAsteptare),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: selected ? AppColors.accent : AppColors.surfaceHigh,
        borderRadius: BorderRadius.circular(9),
        child: InkWell(
          borderRadius: BorderRadius.circular(9),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
            child: Text(label,
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  color:
                      selected ? Colors.white : AppColors.textSecondary,
                )),
          ),
        ),
      ),
    );
  }
}

/// Antetul unei zile, in aceeasi nota cu lista de meciuri.
class _ZiHeader extends StatelessWidget {
  const _ZiHeader({required this.day});

  final DateTime day;

  @override
  Widget build(BuildContext context) {
    final text = DateFormat("EEEE, d MMMM", 'ro').format(day);
    final data = text[0].toUpperCase() + text.substring(1);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 9),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 18,
            decoration: BoxDecoration(
              color: AppColors.highlight,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 10),
          Text(data,
              style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppColors.highlight)),
        ],
      ),
    );
  }
}

class _Linie extends StatelessWidget {
  const _Linie({required this.selectie});

  final SelectionRecord selectie;

  @override
  Widget build(BuildContext context) {
    final s = selectie;
    final culoare = s.isPending
        ? AppColors.textSecondary
        : (s.won! ? AppColors.positive : AppColors.negative);
    final semn = s.isPending
        ? Icons.schedule
        : (s.won! ? Icons.check_rounded : Icons.close_rounded);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 26,
            height: 26,
            decoration: BoxDecoration(
              color: culoare.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(semn, size: 17, color: culoare),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${s.home} – ${s.away}',
                    style: const TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary)),
                const SizedBox(height: 3),
                Text(
                  '${s.marketLabel} · ${(s.probability * 100).toStringAsFixed(0)}%'
                  ' · cotă ${s.odds.toStringAsFixed(2)}',
                  style: const TextStyle(
                      fontSize: 11.5, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 2),
                Text(s.leagueName,
                    style: const TextStyle(
                        fontSize: 10.5, color: AppColors.textSecondary)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(s.score ?? '—',
                  style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                      color: s.isPending ? AppColors.textSecondary : culoare)),
              const SizedBox(height: 3),
              Text(
                s.profitUnits == null
                    ? 'nejucat'
                    : '${s.profitUnits! >= 0 ? '+' : ''}'
                        '${s.profitUnits!.toStringAsFixed(2)}u',
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: s.isPending ? AppColors.textSecondary : culoare),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Gol extends StatelessWidget {
  const _Gol();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Text(
          'Încă nu s-a notat nicio selecție.\n'
          'Apar aici pe măsură ce modelul alege meciuri.',
          textAlign: TextAlign.center,
          style: TextStyle(
              fontSize: 13, color: AppColors.textSecondary, height: 1.5),
        ),
      ),
    );
  }
}
