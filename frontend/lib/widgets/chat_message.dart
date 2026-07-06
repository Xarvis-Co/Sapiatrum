import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';

class ChatMessageWidget extends StatelessWidget {
  final String text;
  final bool isUser;
  final Map<String, dynamic>? citations;

  const ChatMessageWidget({
    Key? key,
    required this.text,
    required this.isUser,
    this.citations,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 10.0),
        padding: const EdgeInsets.all(12.0),
        decoration: BoxDecoration(
          color: isUser 
              ? theme.colorScheme.primary 
              : (isDark ? Colors.grey[800] : Colors.grey[200]),
          borderRadius: BorderRadius.circular(12.0),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            MarkdownBody(
              data: text,
              selectable: true,
              styleSheet: MarkdownStyleSheet.fromTheme(theme).copyWith(
                p: theme.textTheme.bodyMedium?.copyWith(
                  color: isUser 
                      ? theme.colorScheme.onPrimary 
                      : theme.colorScheme.onSurface,
                ),
              ),
              onTapLink: (text, href, title) {
                if (href != null) {
                  launchUrl(Uri.parse(href));
                }
              },
            ),
            if (citations != null && citations!['citations'].isNotEmpty) ...[
              const SizedBox(height: 10),
              const Divider(),
              const Text(
                "Citations",
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              ..._buildCitations(citations!['citations']),
            ],
          ],
        ),
      ),
    );
  }

  List<Widget> _buildCitations(List<dynamic> citationData) {
    return citationData.map((citation) {
      final source = citation['source'] as String?;
      final text = citation['text'] as String?;
      if (source == null) return const SizedBox.shrink();

      return InkWell(
        onTap: () => launchUrl(Uri.parse(source)),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4.0),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.link, size: 16, color: Colors.blue),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  text ?? source,
                  style: const TextStyle(color: Colors.blue, decoration: TextDecoration.underline),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      );
    }).toList();
  }
}
