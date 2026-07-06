import 'package:cloud_firestore/cloud_firestore.dart';

class ChatMessage {
  final String id;
  final String text;
  final String userId;
  final DateTime timestamp;
  final bool isUser;
  final Map<String, dynamic>? citations;

  ChatMessage({
    required this.id,
    required this.text,
    required this.userId,
    required this.timestamp,
    this.isUser = false,
    this.citations,
  });

  factory ChatMessage.fromFirestore(DocumentSnapshot doc) {
    Map data = doc.data() as Map<String, dynamic>;
    return ChatMessage(
      id: doc.id,
      text: data['text'] ?? '',
      userId: data['userId'] ?? '',
      timestamp: (data['timestamp'] as Timestamp).toDate(),
      isUser: data['isUser'] ?? false,
      citations: data['citations'],
    );
  }
}
