import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../models/chat_message.dart';

class ChatHistorySidebar extends StatelessWidget {
  const ChatHistorySidebar({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final authService = Provider.of<AuthService>(context);
    final user = authService.currentUser;
    final theme = Theme.of(context);

    return Container(
      width: 280,
      decoration: BoxDecoration(
        color: theme.canvasColor,
        border: Border(
          right: BorderSide(color: theme.dividerColor, width: 1),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              "Chat History",
              style: theme.textTheme.titleLarge,
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: StreamBuilder<QuerySnapshot>(
              stream: FirebaseFirestore.instance
                  .collection('users')
                  .doc(user?.uid)
                  .collection('chats')
                  .orderBy('timestamp', descending: true)
                  .snapshots(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                final docs = snapshot.data!.docs;
                if (docs.isEmpty) {
                  return const Center(child: Text("No chat history."));
                }
                
                // This is a simplified history. A real app would group messages by session.
                // Here, we just show a list of recent messages.
                return ListView.builder(
                  itemCount: docs.length,
                  itemBuilder: (context, index) {
                    final message = ChatMessage.fromFirestore(docs[index]);
                    return ListTile(
                      leading: Icon(message.isUser ? Icons.person : Icons.computer),
                      title: Text(
                        message.text,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(message.timestamp.toString()),
                      onTap: () {
                        // TODO: Implement loading a past chat session
                      },
                    );
                  },
                );
              },
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: ListTile(
              leading: const Icon(Icons.logout),
              title: const Text("Sign Out"),
              onTap: () => authService.signOut(),
            ),
          ),
        ],
      ),
    );
  }
}
