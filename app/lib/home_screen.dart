import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'about_screen.dart';
import 'detail_screen.dart';
import 'formatting.dart';
import 'models.dart';
import 'recommendations_card.dart';
import 'repository.dart';
import 'search_screen.dart';
import 'theme.dart';
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
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
            child: RecommendationsCard(
              recommendations: bundle.recommendations,
              onTap: (matchId) => _deschideMeci(context, matchId),
            ),
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
          const SliverFillRemaining(
            hasScrollBody: false,
            child: Padding(
              padding: EdgeInsets.all(32),
              child: Center(
                child: Text(
                  'Niciun meci disponibil.\nRuleaza predict.py pentru a genera predictii noi.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textSecondary),
                ),
              ),
            ),
          ),
        for (final day in days) ...[
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 8),
              child: Text(
                _formatDay(day),
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.accent),
              ),
            ),
          ),
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
    if (meci == null) return;
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => DetailScreen(match: meci, store: store)),
    );
  }

  static String _formatDay(DateTime day) {
    final text = DateFormat("EEEE, d MMMM", 'ro').format(day);
    return text[0].toUpperCase() + text.substring(1);
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
              const SizedBox(height: 4),
              Text(
                'Goluri asteptate  ${match.expectedGoalsHome.toStringAsFixed(2)} – '
                '${match.expectedGoalsAway.toStringAsFixed(2)}',
                style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary),
              ),
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
