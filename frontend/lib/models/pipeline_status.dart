class PipelineStatus {
  final String title;
  final String message;

  PipelineStatus({required this.title, required this.message});

  factory PipelineStatus.fromJson(Map<String, dynamic> json) {
    return PipelineStatus(
      title: json['title'] ?? 'Unknown Stage',
      message: json['message'] ?? 'No details available.',
    );
  }
}
