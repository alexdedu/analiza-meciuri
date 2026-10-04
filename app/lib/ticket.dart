import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// Etichete scurte pentru tipul pietei, aceleasi ca in selectii.
const _scurt = {
  '1x2': 'REZ',
  'goluri': 'GOL',
  'cornere': 'CRN',
  'cartonașe': 'CRT',
};

String _pct(double v) => '${(v * 100).toStringAsFixed(0)}%';

/// Cardul de pe prima pagina: biletul dintr-o privire, deschis cu o atingere.
class TicketCard extends StatelessWidget {
  const TicketCard({super.key, required this.ticket, required this.onOpen});

  final Ticket ticket;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onOpen,
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF312E81), Color(0xFF1E1B4B)],
            ),
            border: Border.all(color: AppColors.accent.withValues(alpha: 0.45)),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.confirmation_number_outlined,
                        size: 18, color: AppColors.highlight),
                    const SizedBox(width: 8),
                    const Text('Biletul zilei',
                        style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                            color: Colors.white)),
                    const Spacer(),
                    _Verdict(won: ticket.won),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    _Cifra(
                      valoare: ticket.combinedOdds.toStringAsFixed(2),
                      eticheta: ticket.oddsEstimated ? 'cotă estimată' : 'cotă totală',
                    ),
                    const SizedBox(width: 22),
                    _Cifra(
                      valoare: _pct(ticket.combinedProbability),
                      eticheta: 'șansă',
                    ),
                    const SizedBox(width: 22),
                    _Cifra(
                      valoare: '${ticket.legs.length}',
                      eticheta: 'selecții',
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Tipurile de piata din bilet, ca sa se vada amestecul.
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final leg in ticket.legs)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '${_scurt[leg.family] ?? leg.family} · ${leg.home}',
                          style: const TextStyle(
                              fontSize: 10.5, color: Colors.white70),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                const Row(
                  children: [
                    Text('Vezi selecțiile',
                        style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppColors.highlight)),
                    SizedBox(width: 4),
                    Icon(Icons.chevron_right, size: 18, color: AppColors.highlight),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Cifra extends StatelessWidget {
  const _Cifra({required this.valoare, required this.eticheta});

  final String valoare;
  final String eticheta;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(valoare,
            style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Colors.white,
                height: 1)),
        const SizedBox(height: 3),
        Text(eticheta,
            style: const TextStyle(fontSize: 10.5, color: Colors.white60)),
      ],
    );
  }
}

class _Verdict extends StatelessWidget {
  const _Verdict({required this.won});

  final bool? won;

  @override
  Widget build(BuildContext context) {
    if (won == null) return const SizedBox.shrink();
    final culoare = won! ? AppColors.positive : AppColors.negative;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: culoare.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(won! ? 'CÂȘTIGAT' : 'PIERDUT',
          style: TextStyle(
              fontSize: 10, fontWeight: FontWeight.w800, color: culoare)),
    );
  }
}

/// Ecranul biletului: fiecare selectie, cu drum direct catre meciul ei.
class TicketScreen extends StatelessWidget {
  const TicketScreen({
    super.key,
    required this.ticket,
    required this.record,
    required this.onOpenMatch,
  });

  final Ticket ticket;
  final TicketRecord? record;
  final void Function(BuildContext context, String matchId) onOpenMatch;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Biletul zilei')),
      body: ListView(
        padding: EdgeInsets.fromLTRB(
            16, 4, 16, 28 + MediaQuery.paddingOf(context).bottom),
        children: [
          _Rezumat(ticket: ticket),
          const SizedBox(height: 14),
          for (final leg in ticket.legs)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _Picior(
                leg: leg,
                onTap: () => onOpenMatch(context, leg.matchId),
              ),
            ),
          const SizedBox(height: 6),
          SectionCard(
            title: 'Ce înseamnă cifrele',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Șansele se înmulțesc: ${ticket.legs.length} selecții, fiecare '
                  'în jur de ${_pct(ticket.legs.map((l) => l.probability).reduce((a, b) => a + b) / ticket.legs.length)}, '
                  'fac împreună ${_pct(ticket.combinedProbability)}. După ratele '
                  'măsurate istoric pentru fiecare piață, un astfel de bilet iese '
                  'în ${_pct(ticket.expectedHitRate)} din cazuri.',
                  style: const TextStyle(fontSize: 12.5, height: 1.45),
                ),
                const SizedBox(height: 10),
                Text(
                  ticket.oddsEstimated
                      ? 'Cota totală e estimată: pentru cornere și cartonașe nu '
                          'există cote nicăieri, așa că acolo intră cota corectă '
                          'calculată de model. Cota reală depinde de ce găsești '
                          'la casa ta.'
                      : 'Toate selecțiile au cote reale de pe piață; cota totală '
                          'e produsul lor.',
                  style: const TextStyle(
                      fontSize: 11.5, color: AppColors.textSecondary, height: 1.4),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Selecțiile sunt din meciuri diferite: două piețe ale aceluiași '
                  'meci nu sunt independente, iar înmulțirea șanselor lor ar '
                  'minți. Biletul se face o dată pe zi și nu se mai schimbă.',
                  style: TextStyle(
                      fontSize: 11.5, color: AppColors.textSecondary, height: 1.4),
                ),
              ],
            ),
          ),
          if (record != null && record!.resolved > 0) ...[
            const SizedBox(height: 12),
            SectionCard(
              title: 'Biletele de până acum',
              child: Text(
                '${record!.won} câștigate din ${record!.resolved}'
                '${record!.expected == null ? '' : ' — după ratele măsurate, '
                    'trebuiau să iasă în jur de '
                    '${(record!.expected! * record!.resolved).toStringAsFixed(1)}.'}',
                style: const TextStyle(fontSize: 12.5, height: 1.4),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Rezumat extends StatelessWidget {
  const _Rezumat({required this.ticket});

  final Ticket ticket;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: const LinearGradient(
          colors: [Color(0xFF312E81), Color(0xFF1E1B4B)],
        ),
      ),
      child: Row(
        children: [
          _Cifra(
            valoare: ticket.combinedOdds.toStringAsFixed(2),
            eticheta: ticket.oddsEstimated ? 'cotă estimată' : 'cotă totală',
          ),
          const Spacer(),
          _Cifra(valoare: _pct(ticket.combinedProbability), eticheta: 'șansă model'),
          const Spacer(),
          _Cifra(valoare: _pct(ticket.expectedHitRate), eticheta: 'după istoric'),
        ],
      ),
    );
  }
}

class _Picior extends StatelessWidget {
  const _Picior({required this.leg, required this.onTap});

  final TicketLeg leg;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final areCota = leg.odds != null;
    final culoare = areCota ? AppColors.accentSoft : AppColors.highlight;
    final verdict = leg.won;

    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(13),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: verdict == null
                  ? AppColors.border
                  : (verdict ? AppColors.positive : AppColors.negative)
                      .withValues(alpha: 0.6),
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 40,
                padding: const EdgeInsets.symmetric(vertical: 4),
                decoration: BoxDecoration(
                  color: culoare.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(_scurt[leg.family] ?? leg.family,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: 10, fontWeight: FontWeight.w800, color: culoare)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${leg.home} – ${leg.away}',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary)),
                    const SizedBox(height: 3),
                    Text(leg.marketLabel,
                        style: TextStyle(fontSize: 12.5, color: culoare)),
                    const SizedBox(height: 3),
                    Text(
                      '${leg.leagueName} · ${leg.date.substring(8)}.${leg.date.substring(5, 7)}'
                      '${leg.time.isEmpty ? '' : ' · ${leg.time}'}',
                      style: const TextStyle(
                          fontSize: 10.5, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(_pct(leg.probability),
                      style: TextStyle(
                          fontSize: 15, fontWeight: FontWeight.w800, color: culoare)),
                  const SizedBox(height: 2),
                  Text(
                    areCota
                        ? 'cotă ${leg.odds!.toStringAsFixed(2)}'
                        : 'corect ${leg.fairOdds.toStringAsFixed(2)}',
                    style: const TextStyle(
                        fontSize: 10.5, color: AppColors.textSecondary),
                  ),
                  if (verdict != null) ...[
                    const SizedBox(height: 3),
                    Icon(verdict ? Icons.check_circle : Icons.cancel,
                        size: 16,
                        color: verdict ? AppColors.positive : AppColors.negative),
                  ],
                ],
              ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right, size: 18, color: AppColors.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}
