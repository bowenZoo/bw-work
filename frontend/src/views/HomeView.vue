<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { MessageSquare, Users, Zap } from 'lucide-vue-next';

const router = useRouter();
const topicInput = ref('');

function startDiscussion() {
  if (topicInput.value.trim()) {
    // Navigate to discussion page with topic as query param
    router.push({
      name: 'discussion',
      query: { topic: topicInput.value.trim() },
    });
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    startDiscussion();
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col">
    <!-- Header -->
    <header class="p-6">
      <div class="max-w-4xl mx-auto flex items-center gap-3">
        <div class="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold">AI</span>
        </div>
        <h1 class="text-xl font-semibold text-gray-900">Game Planning AI Team</h1>
      </div>
    </header>

    <!-- Main content -->
    <main class="flex-1 flex items-center justify-center p-6">
      <div class="max-w-2xl w-full">
        <!-- Hero section -->
        <div class="text-center mb-12">
          <h2 class="text-4xl font-bold text-gray-900 mb-4">
            AI-Powered Game Design Discussions
          </h2>
          <p class="text-lg text-gray-600">
            Start a discussion with our AI planning team. System designers, number designers,
            and player advocates will collaborate to help design your game features.
          </p>
        </div>

        <!-- Input section -->
        <div class="bg-white rounded-2xl shadow-xl p-8 mb-12">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            What would you like to discuss?
          </label>
          <div class="flex gap-3">
            <input
              v-model="topicInput"
              type="text"
              placeholder="e.g., Design a gacha system for our RPG game"
              class="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              @keydown="handleKeydown"
            />
            <button
              type="button"
              :disabled="!topicInput.trim()"
              class="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
              @click="startDiscussion"
            >
              Start Discussion
            </button>
          </div>
        </div>

        <!-- Features -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-white rounded-xl p-6 shadow-md">
            <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
              <Users class="w-6 h-6 text-blue-500" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">Multiple Perspectives</h3>
            <p class="text-sm text-gray-600">
              Get input from system designers, number designers, and player advocates.
            </p>
          </div>

          <div class="bg-white rounded-xl p-6 shadow-md">
            <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
              <MessageSquare class="w-6 h-6 text-green-500" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">Real-time Discussion</h3>
            <p class="text-sm text-gray-600">
              Watch the AI team discuss and iterate on your game design ideas.
            </p>
          </div>

          <div class="bg-white rounded-xl p-6 shadow-md">
            <div class="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mb-4">
              <Zap class="w-6 h-6 text-orange-500" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">Instant Results</h3>
            <p class="text-sm text-gray-600">
              Get comprehensive design proposals with balanced perspectives.
            </p>
          </div>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="p-6 text-center text-sm text-gray-500">
      Powered by CrewAI
    </footer>
  </div>
</template>
