#!/usr/bin/env python
"""
Card Resources Audit Script

This script checks all existing card resources in the database,
validates their URLs, and identifies which cards need fixing.
It can also automatically fix invalid resources if requested.
"""

import os
import sys
import json
import asyncio
import argparse
from typing import Dict, List, Optional, Any, Tuple
import logging

# Add the root directory to path to allow importing from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Card
from app.utils.url_validator import is_valid_url, get_valid_resources
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('card_resources_audit.log')
    ]
)
logger = logging.getLogger(__name__)

def get_all_cards(db: Session, limit: Optional[int] = None) -> List[Card]:
    """Get all cards from the database, optionally limited"""
    query = db.query(Card)
    if limit:
        query = query.limit(limit)
    return query.all()

async def validate_card_resources(card: Card) -> Tuple[bool, List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Validate the resources for a single card
    
    Returns:
        Tuple containing:
        - Whether all resources are valid
        - List of valid resources
        - List of invalid resources
    """
    if not card.resources:
        return True, [], []
    
    try:
        # Parse resources from JSON if stored as string
        resources = card.resources
        if isinstance(resources, str):
            resources = json.loads(resources)
        
        # Handle empty resources
        if not resources:
            return True, [], []
        
        valid_resources = []
        invalid_resources = []
        
        for resource in resources:
            if isinstance(resource, dict) and 'url' in resource:
                url = resource.get('url')
                if url and is_valid_url(url):
                    valid_resources.append(resource)
                else:
                    invalid_resources.append(resource)
            else:
                # Skip resources without URL
                continue
        
        all_valid = len(invalid_resources) == 0
        return all_valid, valid_resources, invalid_resources
    
    except Exception as e:
        logger.error(f"Error validating resources for card ID {card.id}: {e}")
        return False, [], []

async def fix_card_resources(
    db: Session, 
    card: Card, 
    invalid_resources: List[Dict[str, str]],
    valid_resources: List[Dict[str, str]] = None
) -> Tuple[bool, List[Dict[str, str]]]:
    """
    Fix invalid resources for a card using Google Search
    
    Returns:
        Tuple containing:
        - Whether the fix was successful
        - The new resources list
    """
    try:
        # Create search context from card data
        context = f"{card.keyword} {card.question}"
        
        # Get enhanced resources (valid existing ones + new ones from search)
        existing_resources = valid_resources or []
        if invalid_resources:
            # Add invalid resources to the list, they might be partially valid
            # or potentially fixable with slight URL modifications
            existing_resources.extend(invalid_resources)
        
        enhanced_resources = get_valid_resources(
            keyword=card.keyword,
            context=context,
            existing_resources=existing_resources
        )
        
        # Update the card in the database
        if isinstance(card.resources, str):
            # If resources were stored as JSON string, convert back
            card.resources = json.dumps(enhanced_resources)
        else:
            card.resources = enhanced_resources
        
        db.add(card)
        db.commit()
        
        return True, enhanced_resources
    
    except Exception as e:
        logger.error(f"Error fixing resources for card ID {card.id}: {e}")
        db.rollback()
        return False, []

async def audit_resources(
    limit: Optional[int] = None, 
    fix: bool = False,
    summary_only: bool = False
) -> Dict[str, Any]:
    """
    Audit all card resources in the database
    
    Args:
        limit: Maximum number of cards to check
        fix: Whether to automatically fix invalid resources
        summary_only: Whether to only return summary statistics
    
    Returns:
        Dictionary with audit results
    """
    db = SessionLocal()
    try:
        cards = get_all_cards(db, limit)
        logger.info(f"Found {len(cards)} cards to audit")
        
        valid_cards = []
        invalid_cards = []
        fixed_cards = []
        failed_fixes = []
        
        for card in cards:
            all_valid, valid_resources, invalid_resources = await validate_card_resources(card)
            
            if all_valid:
                valid_cards.append(card.id)
                logger.debug(f"Card ID {card.id} has valid resources")
            else:
                logger.info(f"Card ID {card.id} has {len(invalid_resources)} invalid resources")
                invalid_cards.append({
                    "id": card.id,
                    "keyword": card.keyword,
                    "valid_resources": valid_resources,
                    "invalid_resources": invalid_resources
                })
                
                if fix:
                    success, new_resources = await fix_card_resources(
                        db, card, invalid_resources, valid_resources
                    )
                    if success:
                        fixed_cards.append({
                            "id": card.id,
                            "keyword": card.keyword,
                            "original_resources": card.resources if isinstance(card.resources, list) else json.loads(card.resources) if isinstance(card.resources, str) else [],
                            "new_resources": new_resources
                        })
                        logger.info(f"Successfully fixed resources for card ID {card.id}")
                    else:
                        failed_fixes.append(card.id)
                        logger.error(f"Failed to fix resources for card ID {card.id}")
        
        # Prepare summary report
        total_cards = len(cards)
        total_valid = len(valid_cards)
        total_invalid = len(invalid_cards)
        total_fixed = len(fixed_cards)
        total_failed_fixes = len(failed_fixes)
        
        summary = {
            "total_cards": total_cards,
            "valid_cards": total_valid,
            "invalid_cards": total_invalid,
            "percentage_valid": round(total_valid / total_cards * 100, 2) if total_cards > 0 else 0,
            "fixed_cards": total_fixed,
            "failed_fixes": total_failed_fixes
        }
        
        # Prepare detailed report
        if summary_only:
            result = {
                "summary": summary
            }
        else:
            result = {
                "summary": summary,
                "valid_card_ids": valid_cards,
                "invalid_cards": invalid_cards,
                "fixed_cards": fixed_cards,
                "failed_fix_ids": failed_fixes
            }
            
        return result
    
    finally:
        db.close()

async def main():
    parser = argparse.ArgumentParser(description="Audit and fix card resources")
    parser.add_argument("--limit", type=int, help="Maximum number of cards to check")
    parser.add_argument("--fix", action="store_true", help="Automatically fix invalid resources")
    parser.add_argument("--summary", action="store_true", help="Show only summary statistics")
    parser.add_argument("--output", help="Output file for the audit results")

    args = parser.parse_args()
    
    try:
        logger.info("Starting card resources audit")
        result = await audit_resources(
            limit=args.limit,
            fix=args.fix,
            summary_only=args.summary
        )
        
        # Print summary to console
        summary = result["summary"]
        print("\n===== Card Resources Audit Summary =====")
        print(f"Total cards checked: {summary['total_cards']}")
        print(f"Valid cards: {summary['valid_cards']} ({summary['percentage_valid']}%)")
        print(f"Invalid cards: {summary['invalid_cards']}")
        
        if args.fix:
            print(f"Cards fixed: {summary['fixed_cards']}")
            print(f"Failed fixes: {summary['failed_fixes']}")
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\nAudit results saved to {args.output}")
            
        logger.info("Card resources audit completed")
            
    except Exception as e:
        logger.error(f"Error during audit: {e}")
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 