import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'search_links.dart';
import 'theme.dart';
import 'widgets.dart';

/// Butoanele de cautare, folosite si pe ecranul unui meci, si pe cel de cautare
/// manuala. Deschid browserul telefonului; aplicatia nu citeste nimic din Google.
class SearchCard extends StatelessWidget {
  const SearchCard({
    super.key,
    required this.home,
    required this.away,
    this.title = 'Caută online',
    this.subtitle,
  });

  final String home;
  final String away;
  final String title;
  final String? subtitle;

  Future<void> _open(BuildContext context, SearchKind kind) async {
    final url = buildSearchUrl(home, away, kind);
    final messenger = ScaffoldMessenger.of(context);
    final ok = await launchUrl(url, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Nu am putut deschide browserul.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final activ = canSearch(home, away);
    return SectionCard(
      title: title,
      subtitle: subtitle,
      child: Column(
        children: [
          for (final kind in SearchKind.values)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _SearchButton(
                kind: kind,
                enabled: activ,
                onTap: () => _open(context, kind),
              ),
            ),
        ],
      ),
    );
  }
}

class _SearchButton extends StatelessWidget {
  const _SearchButton({required this.kind, required this.enabled, required this.onTap});

  final SearchKind kind;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final culoare = kind == SearchKind.ponturi ? AppColors.textSecondary : AppColors.accentSoft;
    return Opacity(
      opacity: enabled ? 1 : 0.4,
      child: Material(
        color: AppColors.surfaceHigh,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: enabled ? onTap : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
            child: Row(
              children: [
                Icon(
                  switch (kind) {
                    SearchKind.general => Icons.travel_explore,
                    SearchKind.statistici => Icons.bar_chart,
                    SearchKind.ponturi => Icons.forum_outlined,
                  },
                  size: 18,
                  color: culoare,
                ),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(kind.label,
                          style: TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w600, color: culoare)),
                      const SizedBox(height: 2),
                      Text(kind.hint,
                          style: const TextStyle(
                              fontSize: 11, color: AppColors.textSecondary)),
                    ],
                  ),
                ),
                const Icon(Icons.open_in_new, size: 15, color: AppColors.textSecondary),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
