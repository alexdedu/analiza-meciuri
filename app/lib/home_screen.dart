import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'about_screen.dart';
import 'detail_screen.dart';
import 'formatting.dart';
import 'models.dart';
import 'picks_card.dart';
import 'repository.dart';
import 'search_screen.dart';
import 'theme.dart';
import 'ticket.dart';
import 'track_record_card.dart';
import 'widgets.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<(LoadResult, OddsStore)> _future;
  String? _leagueFilter;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<(LoadResult, OddsStore)> _load() async {
    final result = await PredictionRepository().load();
    final store = await OddsStore.create();
    return (result, store);
  }

  /// Tragerea in jos reincarca de la sursa. Asteptam terminarea, ca indicatorul
  /// de reimprospatare sa dispara abia cand chiar avem datele noi.
  Future<void> _refresh() async {
    final future = _load();
    setState(() => _future = future);
    await future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<(LoadResult, OddsStore)>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return _ErrorView(
              error: snapshot.error!,
              onRetry: () => setState(() => _future = _load()),
            );
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final (result, store) = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            color: AppColors.accent,
            backgroundColor: AppColors.surface,
            child: _MatchList(
              result: result,
              store: store,
              leagueFilter: _leagueFilter,
              onFilterChanged: (value) => setState(() => _leagueFilter = value),
            ),
          );
        },
      ),
    );
  }
}

class _MatchList extends StatelessWidget {
  const _MatchList({
    required this.result,
    required this.store,
    required this.leagueFilter,
    required this.onFilterChanged,
  });

  final LoadResult result;
  final OddsStore store;
  final String? leagueFilter;
  final ValueChanged<String?> onFilterChanged;

  PredictionBundle get bundle => result.bundle;

  @override
  Widget build(BuildContext context) {
    final matches = leagueFilter == null
        ? bundle.matches
        : bundle.matches.where((m) => m.league == leagueFilter).toList();

    final leagues = {for (final m in bundle.matches) m.league: m.leagueName};

    // Grupam pe zi, ca sa avem antete de tip "Miercuri, 16 septembrie".
    final byDate = <DateTime, List<MatchPrediction>>{};
    for (final m in matches) {
      byDate.putIfAbsent(m.date, () => []).add(m);
    }
    final days = byDate.keys.toList()..sort();

    return CustomScrollView(
      // Permite tragerea in jos chiar si cand lista e scurta sau goala.
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        SliverAppBar.large(
          title: const Text('Analiza meciurilor'),
          actions: [
            IconButton(
              icon: const Icon(Icons.search),
              tooltip: 'Caută alt meci',
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SearchScreen()),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.info_outline),
              tooltip: 'Despre model',
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => AboutScreen(bundle: bundle)),
              ),
            ),
          ],
        ),
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: _HonestyBanner(result: result),
          ),
        ),
        if (bundle.ticket != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: TicketCard(
                ticket: bundle.ticket!,
                onOpen: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => TicketScreen(
                    ticket: bundle.ticket!,
                    record: bundle.ticketRecord,
                    onOpenMatch: _deschideMeci,
                  ),
                )),
              ),
            ),
          ),
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
            child: PicksCard(
              matches: bundle.recommendedMatches,
              countsRecord: bundle.trackRecord?.counts,
              onTap: (matchId) => _deschideMeci(context, matchId),
            ),
          ),
        ),
        if (bundle.trackRecord != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: TrackRecordCard(record: bundle.trackRecord!),
            ),
          ),
        if (leagues.length > 1)
          SliverToBoxAdapter(
            child: SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                children: [
                  _FilterChip(
                    label: 'Toate',
                    selected: leagueFilter == null,
                    onTap: () => onFilterChanged(null),
                  ),
                  for (final entry in leagues.entries)
                    _FilterChip(
                      label: entry.value,
                      selected: leagueFilter == entry.key,
                      onTap: () => onFilterChanged(entry.key),
                    ),
                ],
              ),
            ),
          ),
        if (matches.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Center(child: EmptyState(nextRound: bundle.nextRound)),
            ),
          ),
        for (final day in days) ...[
          SliverToBoxAdapter(child: DayHeader(day: day)),
          SliverList.separated(
            itemCount: byDate[day]!.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, i) => Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: _MatchCard(match: byDate[day]![i], store: store),
            ),
          ),
        ],
        // Android deseneaza continutul sub bara de navigare (edge-to-edge), deci
        // ultimul card ar fi acoperit. Adaugam exact inaltimea barei telefonului.
        SliverToBoxAdapter(
          child: SizedBox(height: 28 + MediaQuery.paddingOf(context).bottom),
        ),
      ],
    );
  }

  /// Din recomandare se ajunge la meciul din care a venit.
  void _deschideMeci(BuildContext context, String matchId) {
    final meci = bundle.matches.where((m) => m.id == matchId).firstOrNull;
    if (meci == null) {
      // Biletul zilei ramane neschimbat toata ziua, deci poate trimite catre
      // un meci deja jucat, care a iesit din lista.
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Meciul s-a jucat și nu mai e în listă.'),
      ));
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => DetailScreen(match: meci, store: store)),
    );
  }

}

/// Ce se afiseaza cand nu e niciun meci de aratat.
///
/// Diferenta dintre "e pauza" si "s-a stricat ceva" e tot ce conteaza aici:
/// in pauza, o lista goala e raspunsul corect, iar utilizatorul trebuie sa
/// stie cand sa revina.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.nextRound});

  final NextRound? nextRound;

  @override
  Widget build(BuildContext context) {
    final r = nextRound;
    if (r == null) {
      return const Text(
        'Niciun meci în următoarele 3 zile.\n'
        'Lista se actualizează singură de câteva ori pe zi.',
        textAlign: TextAlign.center,
        style: TextStyle(color: AppColors.textSecondary),
      );
    }

    final acum = DateTime.now();
    final zile = DateTime(r.date.year, r.date.month, r.date.day)
        .difference(DateTime(acum.year, acum.month, acum.day))
        .inDays;
    final text = DateFormat("EEEE, d MMMM", 'ro').format(r.date);
    final data = text[0].toUpperCase() + text.substring(1);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.event_busy, size: 34, color: AppColors.textSecondary),
        const SizedBox(height: 14),
        const Text('Pauză competițională',
            style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary)),
        const SizedBox(height: 8),
        const Text('Nu se joacă nimic în campionatele urmărite.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          decoration: BoxDecoration(
            color: AppColors.surfaceHigh,
            borderRadius: BorderRadius.circular(11),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: [
              const Text('Următoarele meciuri',
                  style: TextStyle(fontSize: 11, color: AppColors.textSecondary)),
              const SizedBox(height: 4),
              Text(data,
                  style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                      color: AppColors.highlight)),
              if (zile > 0) ...[
                const SizedBox(height: 3),
                Text(zile == 1 ? 'mâine' : 'peste $zile zile',
                    style: const TextStyle(
                        fontSize: 11.5, color: AppColors.textSecondary)),
              ],
              if (r.competitions.isNotEmpty) ...[
                const SizedBox(height: 7),
                Text(r.competitions.join(' · '),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 11.5, color: AppColors.textPrimary)),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),
        const Text('Predicțiile apar singure cu trei zile înainte.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
      ],
    );
  }
}

/// Antetul unei zile din lista.
///
/// Intr-o fereastra de trei zile, "AZI" si "MAINE" spun mai mult dintr-o
/// privire decat data calendaristica, asa ca apar primele.
class DayHeader extends StatelessWidget {
  const DayHeader({super.key, required this.day});

  final DateTime day;

  @override
  Widget build(BuildContext context) {
    final acum = DateTime.now();
    final azi = DateTime(acum.year, acum.month, acum.day);
    final diferenta = DateTime(day.year, day.month, day.day).difference(azi).inDays;
    final eticheta = switch (diferenta) {
      0 => 'AZI',
      1 => 'MÂINE',
      _ => null,
    };

    final text = DateFormat("EEEE, d MMMM", 'ro').format(day);
    final data = text[0].toUpperCase() + text.substring(1);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 22, 16, 10),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 22,
            decoration: BoxDecoration(
              color: AppColors.highlight,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 10),
          if (eticheta != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: AppColors.highlight,
                borderRadius: BorderRadius.circular(5),
              ),
              child: Text(eticheta,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                    color: AppColors.background,
                  )),
            ),
            const SizedBox(width: 9),
          ],
          Flexible(
            child: Text(
              data,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.highlight,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _HonestyBanner extends StatelessWidget {
  const _HonestyBanner({required this.result});

  final LoadResult result;

  PredictionBundle get bundle => result.bundle;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => AboutScreen(bundle: bundle)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppColors.accent.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.query_stats, color: AppColors.accent, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Probabilitati, nu pronosticuri sigure',
                        style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    const Text('Modelul e bine calibrat, dar nu bate casele de pariuri.',
                        style: TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
                    const SizedBox(height: 3),
                    Text(
                        '${freshnessLabel(bundle.generatedAt)} · ${result.source.label}',
                        style: const TextStyle(fontSize: 10.5, color: AppColors.accentSoft)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: AppColors.textSecondary, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(label,
            style: TextStyle(
              fontSize: 12,
              color: selected ? AppColors.accentSoft : AppColors.textSecondary,
              fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
            )),
        selected: selected,
        onSelected: (_) => onTap(),
        showCheckmark: false,
      ),
    );
  }
}

class _MatchCard extends StatelessWidget {
  const _MatchCard({required this.match, required this.store});

  final MatchPrediction match;
  final OddsStore store;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => DetailScreen(match: match, store: store)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(match.leagueName,
                      style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                  const Spacer(),
                  if (match.time.isNotEmpty)
                    Text(match.time,
                        style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                  const SizedBox(width: 8),
                  ConfidenceBadge(confidence: match.confidence, compact: true),
                ],
              ),
              const SizedBox(height: 10),
              Text('${match.home}  –  ${match.away}',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
              const SizedBox(height: 7),
              // Cifrele care conteaza, direct in lista: altfel ar trebui
              // deschis fiecare meci ca sa se vada ce are de oferit.
              _Cifre(match: match),
              const SizedBox(height: 12),
              ProbabilityBar(
                home: match.p('p_home'),
                draw: match.p('p_draw'),
                away: match.p('p_away'),
              ),
              const SizedBox(height: 7),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _Legend(color: AppColors.homeWin, text: '1  ${_pct(match.p('p_home'))}'),
                  _Legend(color: AppColors.draw, text: 'X  ${_pct(match.p('p_draw'))}'),
                  _Legend(color: AppColors.awayWin, text: '2  ${_pct(match.p('p_away'))}'),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _pct(double v) => '${(v * 100).toStringAsFixed(0)}%';
}

/// Golurile, cornerele si cartonasele asteptate, pe un singur rand.
///
/// Cornerele si cartonasele lipsesc la meciurile pentru care sursa nu le are
/// (Romania, cupele, nationalele) -- acolo raman doar golurile.
class _Cifre extends StatelessWidget {
  const _Cifre({required this.match});

  final MatchPrediction match;

  @override
  Widget build(BuildContext context) {
    final cornere = match.extraMarkets?.corners;
    final cartonase = match.extraMarkets?.cards;

    return Wrap(
      spacing: 14,
      runSpacing: 4,
      children: [
        _Cifra(
          eticheta: 'goluri',
          valoare: '${match.expectedGoalsHome.toStringAsFixed(1)}–'
              '${match.expectedGoalsAway.toStringAsFixed(1)}',
        ),
        if (cornere != null)
          _Cifra(
            eticheta: 'cornere',
            valoare: '${cornere.expectedHome.toStringAsFixed(1)}–'
                '${cornere.expectedAway.toStringAsFixed(1)}',
          ),
        if (cartonase != null)
          _Cifra(
            eticheta: 'cartonașe',
            valoare: cartonase.expectedTotal.toStringAsFixed(1),
          ),
      ],
    );
  }
}

class _Cifra extends StatelessWidget {
  const _Cifra({required this.eticheta, required this.valoare});

  final String eticheta;
  final String valoare;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$eticheta ',
            style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
        Text(valoare,
            style: const TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary)),
      ],
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.color, required this.text});

  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 5),
        Text(text, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary)),
      ],
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: AppColors.negative, size: 40),
            const SizedBox(height: 14),
            const Text('Nu am putut incarca predictiile',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text('$error',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
            const SizedBox(height: 18),
            FilledButton(onPressed: onRetry, child: const Text('Incearca din nou')),
          ],
        ),
      ),
    );
  }
}
