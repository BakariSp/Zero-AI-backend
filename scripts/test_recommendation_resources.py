#!/usr/bin/env python
"""
Test URL Validation in Recommendation System

This script tests the URL validation for card resources in the recommendation system
by simulating card generation for a test learning path/section.
"""

import os
import sys
import asyncio
import json
import argparse
from typing import Dict, List, Any

# Add the root directory to path to allow importing from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, Base, engine
from app.services.learning_path_planner import LearningPathPlannerService
from app.utils.url_validator import is_valid_url, get_valid_resources
from app.models import LearningPath, Course, CourseSection, Card

async def test_card_generation_with_resource_validation(
    topic: str, 
    num_cards: int = 2,
    course_title: str = "Test Course",
    difficulty: str = "intermediate"
):
    """Test card generation with resource validation"""
    
    print(f"\n=== Generating {num_cards} cards for topic: '{topic}' ===\n")
    
    # Initialize the service
    service = LearningPathPlannerService()
    
    if not service.card_manager or not service.card_manager.card_generator:
        print("ERROR: Failed to initialize CardGenerator")
        return
    
    # Generate cards
    try:
        cards = await service.card_manager.card_generator.generate_multiple_cards_from_topic(
            topic=topic,
            num_cards=num_cards,
            course_title=course_title,
            difficulty=difficulty
        )
        
        print(f"✅ Generated {len(cards)} cards")
        
        for i, card in enumerate(cards):
            print(f"\n--- Card {i+1}: {card.keyword} ---")
            
            # Extract resources
            resources = getattr(card, 'resources', [])
            if hasattr(card, 'dict'):
                card_dict = card.dict()
                resources = card_dict.get('resources', [])
            
            print(f"Original resources: {len(resources)}")
            
            # Print resource details
            if resources:
                for j, resource in enumerate(resources):
                    url = resource.get('url', 'No URL')
                    title = resource.get('title', 'No Title')
                    is_valid = is_valid_url(url) if url else False
                    status = "✅ Valid" if is_valid else "❌ Invalid"
                    print(f"  {j+1}. {status} - {title}: {url}")
            else:
                print("  No resources found")
            
            # Validate and enhance resources
            print("\nValidating and enhancing resources...")
            validated_resources = await asyncio.to_thread(
                get_valid_resources,
                keyword=card.keyword,
                context=topic,
                existing_resources=resources
            )
            
            print(f"Enhanced resources: {len(validated_resources)}")
            
            # Print enhanced resource details
            if validated_resources:
                for j, resource in enumerate(validated_resources):
                    url = resource.get('url', 'No URL')
                    title = resource.get('title', 'No Title')
                    is_valid = is_valid_url(url) if url else False
                    status = "✅ Valid" if is_valid else "❌ Invalid"
                    print(f"  {j+1}. {status} - {title}: {url}")
            else:
                print("  No enhanced resources found")
            
            # Compare
            original_valid = sum(1 for r in resources if r.get('url') and is_valid_url(r.get('url')))
            enhanced_valid = sum(1 for r in validated_resources if r.get('url') and is_valid_url(r.get('url')))
            
            print(f"\nValid URLs: {original_valid}/{len(resources)} original → {enhanced_valid}/{len(validated_resources)} enhanced")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

async def test_path_structure_cards(num_cards_per_section: int = 2):
    """Generate a test learning path structure and validate resources for its cards"""
    
    print("\n=== Testing Learning Path Structure Card Generation ===\n")
    
    # Create a test learning path structure
    learning_path_structure = {
        "learning_path": {
            "id": 999,  # Dummy ID
            "title": "Test Learning Path",
            "description": "Test Description",
            "difficulty_level": "intermediate"
        },
        "courses": [
            {
                "course_id": 999,  # Dummy ID
                "title": "Test Course",
                "sections": [
                    {
                        "section_id": 999,  # Dummy ID
                        "title": "Python Programming Basics",
                        "keywords": ["Python", "Programming", "Variables", "Functions"]
                    },
                    {
                        "section_id": 998,  # Dummy ID
                        "title": "Data Structures",
                        "keywords": ["Lists", "Dictionaries", "Tuples", "Sets"]
                    }
                ]
            }
        ]
    }
    
    # Initialize the service
    service = LearningPathPlannerService()
    
    if not service.card_manager or not service.card_manager.card_generator:
        print("ERROR: Failed to initialize CardGenerator")
        return
    
    # Create a mock progress callback
    def progress_callback(completed_count):
        print(f"Progress: {completed_count} cards completed")
    
    try:
        # Override the create_card function to not interact with the database
        from app.cards.crud import create_card as original_create_card
        from app.sections.crud import add_card_to_section as original_add_card_to_section
        
        # Mock functions
        cards_created = []
        
        def mock_create_card(_, card_data):
            """Mock implementation that doesn't touch the database"""
            card_dict = card_data.dict() if hasattr(card_data, 'dict') else card_data
            card_id = len(cards_created) + 1  # Dummy ID
            
            # Create a Card-like object
            class MockCard:
                def __init__(self, id, keyword, resources):
                    self.id = id
                    self.keyword = keyword
                    self.resources = resources
            
            card = MockCard(
                id=card_id,
                keyword=card_dict.get('keyword', 'Unknown'),
                resources=card_dict.get('resources', [])
            )
            
            cards_created.append(card)
            return card
        
        def mock_add_card_to_section(_, section_id, card_id, order=1):
            """Mock implementation that doesn't touch the database"""
            return True
        
        # Monkeypatch the functions
        import app.cards.crud
        import app.sections.crud
        app.cards.crud.create_card = mock_create_card
        app.sections.crud.add_card_to_section = mock_add_card_to_section
        
        # Generate cards for the test path
        await service.generate_cards_for_learning_path(
            db=None,  # Not used in mocked functions
            learning_path_structure=learning_path_structure,
            progress_callback=progress_callback,
            cards_per_section=num_cards_per_section
        )
        
        print(f"\n✅ Generated a total of {len(cards_created)} cards")
        
        # Analyze resources
        total_resources = 0
        valid_resources = 0
        
        for i, card in enumerate(cards_created):
            resources = card.resources
            if isinstance(resources, str):
                try:
                    resources = json.loads(resources)
                except:
                    resources = []
            
            total_resources += len(resources)
            valid_count = sum(1 for r in resources if r.get('url') and is_valid_url(r.get('url')))
            valid_resources += valid_count
            
            print(f"\nCard {i+1}: {card.keyword}")
            print(f"Valid Resources: {valid_count}/{len(resources)}")
            
            # Print resource details
            for j, resource in enumerate(resources):
                url = resource.get('url', 'No URL')
                title = resource.get('title', 'No Title')
                is_valid = is_valid_url(url) if url else False
                status = "✅ Valid" if is_valid else "❌ Invalid"
                print(f"  {j+1}. {status} - {title}: {url}")
        
        # Restore original functions
        app.cards.crud.create_card = original_create_card
        app.sections.crud.add_card_to_section = original_add_card_to_section
        
        # Check if total_resources is zero to avoid division by zero
        if total_resources > 0:
            valid_percentage = (valid_resources / total_resources) * 100
        else:
            valid_percentage = 0

        print(f"\nSummary: {valid_resources}/{total_resources} valid resources ({valid_percentage:.1f}% valid)")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

async def main():
    parser = argparse.ArgumentParser(description="Test URL validation in recommendation system")
    
    # Define available tests
    subparsers = parser.add_subparsers(dest="command", help="Test to run")
    
    # Card generation test
    card_parser = subparsers.add_parser("card", help="Test card generation with resource validation")
    card_parser.add_argument("topic", help="Topic for card generation")
    card_parser.add_argument("--num", type=int, default=2, help="Number of cards to generate (default: 2)")
    card_parser.add_argument("--course", default="Test Course", help="Course title (default: 'Test Course')")
    
    # Path structure test
    path_parser = subparsers.add_parser("path", help="Test path structure card generation")
    path_parser.add_argument("--num", type=int, default=2, help="Number of cards per section (default: 2)")
    
    args = parser.parse_args()
    
    if args.command == "card":
        await test_card_generation_with_resource_validation(
            topic=args.topic,
            num_cards=args.num,
            course_title=args.course
        )
    elif args.command == "path":
        await test_path_structure_cards(args.num)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main()) 